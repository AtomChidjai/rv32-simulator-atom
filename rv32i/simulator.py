"""The public simulator orchestrator and its three execution engines."""

import sys
import time
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass

from .cpu import Processor
from .memory import Memory
from .cache import Cache
from .decoder import Decoder
from .csr import CSRFile
from .builder import build
from .elf_loader import load_elf
from .bin_loader import load_bin
from .constants import INSTRUCTION_TYPE, INTERRUPT_PRIORITY
from .exceptions import TrapException, illegal_instruction
from .devices import (
    raise_external_irq,
    raise_software_irq,
    register_default_devices,
)
from .pipeline import (
    BranchPredictionSnapshot,
    Latch,
    PipelineLatchSnapshot,
    PipelineSnapshot,
    S_IF,
    S_ID,
    S_EX,
    S_MEM,
)
from .execution import (
    compute_rtype,
    compute_itype_imm,
    compute_load,
    compute_store,
    compute_branch,
    compute_jal,
    compute_jalr,
    compute_utype,
    compute_csr,
    compute_mret,
    compute_ecall,
    compute_ebreak,
    compute_fence,
    ComputeResult,
)

_ILLEGAL_NAMES = frozenset(("unknown", "reserved"))


@dataclass
class MCInstr:
    """One instruction's variable-length multi-cycle state."""

    pc: int
    instruction: int
    inst_size: int
    decoded: dict
    stages: list[str]
    stage_idx: int = -1
    rd: int | None = None
    result: int | None = None
    next_pc: int | None = None
    mem_op: dict | None = None
    commit_stage: str | None = None
    csr_write: tuple[int, int] | None = None
    halt: bool = False
    trap: object | None = None
    stall_info: tuple[str, int] | None = None


class Simulator:
    def __init__(
        self,
        verbose_decoder: bool = False,
        trace: bool = False,
        max_cycles: int = 100,
        verbose_register: bool = False,
        cache_size: int = 32 * 1024,
        cache_ways: int = 1,
        cache_block_size: int = 64,
        cache_policy: str = "fifo",
        icache_miss_stall: int = 0,
        dcache_miss_stall: int = 0,
        forwarding: bool = True,
        branch_predict: str = "nottaken",
    ) -> None:
        self.proc = Processor()
        self.mem = Memory()
        self._cache_size = cache_size
        self._cache_ways = cache_ways
        self._cache_block_size = cache_block_size
        self._cache_policy = cache_policy
        self.icache_miss_stall = max(0, icache_miss_stall)
        self.dcache_miss_stall = max(0, dcache_miss_stall)
        self.forwarding = bool(forwarding)
        self.branch_predict = branch_predict if branch_predict in ("nottaken", "taken") else "nottaken"
        self.icache = Cache(self.mem, cache_size, cache_block_size, cache_ways, cache_policy)
        self.dcache = Cache(self.mem, cache_size, cache_block_size, cache_ways, cache_policy)
        self.decoder = Decoder(verbose=verbose_decoder)
        self.csr = CSRFile()
        self.trace = trace
        self.max_cycles = max_cycles
        self._loaded = False
        self._entry_point = 0
        self.verbose_register = verbose_register
        self.history: list[dict] = []
        self.timer = None
        self.console_buffer: list[str] = []
        self.on_console_write = None
        self._waiting_for_input = False
        self._mc: MCInstr | None = None
        self._Latch = Latch
        self.if_id: Latch = Latch.bubble_slot()
        self.id_ex: Latch = Latch.bubble_slot()
        self.ex_mem: Latch = Latch.bubble_slot()
        self.mem_wb: Latch = Latch.bubble_slot()
        self.pipe_stalls: int = 0
        self.pipe_flushes: int = 0
        self.pipe_branches: int = 0
        self.pipe_predicted_taken: int = 0
        self.pipe_predicted_not_taken: int = 0
        self.pipe_predictions_correct: int = 0
        self.pipe_predictions_incorrect: int = 0
        self._pipe_active: bool = False
        self._pipe_mem_stalled: bool = False
        self._pipe_icache_stall_remaining: int = 0
        self._pipe_icache_stall_total: int = 0
        self._pipe_icache_pending: Latch | None = None
        self._pipe_dcache_stall_remaining: int = 0
        self._pipe_dcache_stall_total: int = 0
        self._pipe_dcache_pending: Latch | None = None
        self._pipe_next_fetch_id: int = 0
        self._pipe_fetch_trap: TrapException | None = None
        self._pipe_fetch_trap_pc: int | None = None
        self.pipe_trace: list[dict] = []

    def load(self, c_file: str) -> dict:
        result = build(c_file)
        elf_info = load_elf(result["elf_file"])
        self.load_program(result["bin_file"], elf_info)
        return {**elf_info, "build": result}

    def load_program(
        self,
        bin_file: str,
        elf_info: dict,
        on_console_read: Callable[[], str] | None = None,
    ) -> None:
        """Load compiled artifacts and initialize a fresh runnable machine."""
        self.mem.reset()
        self.reset(pc=elf_info["entry_point"])
        load_bin(self.mem, bin_file, base_address=elf_info["load_addr"])
        self.proc.write_register(2, elf_info["stack_top"])
        gp = elf_info.get("global_pointer")
        if gp is not None:
            self.proc.write_register(3, gp)
        self._entry_point = elf_info["entry_point"]
        self._loaded = True
        self.console_buffer.clear()
        self.timer = register_default_devices(
            self.mem,
            self.csr,
            on_console_write=self.on_console,
            on_console_read=on_console_read,
        )

    @property
    def loaded(self) -> bool:
        return self._loaded

    @property
    def entry_point(self) -> int:
        return self._entry_point

    @property
    def waiting_for_input(self) -> bool:
        return self._waiting_for_input or self.mem.waiting_for_input

    def resume_input(self) -> None:
        """Clear a console-input stall so the active engine can replay."""
        self._waiting_for_input = False
        self.mem.resume_input()

    def memory_snapshot(self) -> dict[int, bytes]:
        """Return a detached snapshot of allocated program/data memory."""
        return self.mem.snapshot_chunks()

    def restore_memory(self, snapshot: dict[int, bytes]) -> None:
        """Restore program/data memory without replacing registered devices."""
        self.mem.restore_chunks(snapshot)

    def csr_snapshot(self) -> dict[int, int]:
        """Return a detached snapshot of implemented CSRs."""
        return self.csr.snapshot()

    def multicycle_state(self) -> MCInstr | None:
        """Return a detached observer copy of the active multi-cycle instruction."""
        return deepcopy(self._mc)

    def has_in_flight_work(self) -> bool:
        """Return whether switching execution engines would abandon work."""
        return (
            self._mc is not None
            or not self.pipeline_state().drained
            or self.waiting_for_input
        )

    def raise_external_interrupt(self) -> None:
        raise_external_irq(self.csr)

    def raise_software_interrupt(self) -> None:
        raise_software_irq(self.csr)

    def on_console(self, ch: str) -> None:
        self.console_buffer.append(ch)
        if self.on_console_write:
            self.on_console_write(ch)

    def reset(self, pc: int | None = None) -> None:
        self.proc.reset(pc=pc)
        self.csr.reset()
        if self.timer is not None:
            self.timer.reset()
        self.mem.resume_input()
        self.icache.flush()
        self.dcache.flush()
        self.history.clear()
        self._waiting_for_input = False
        self._mc = None
        self.if_id = self._Latch.bubble_slot()
        self.id_ex = self._Latch.bubble_slot()
        self.ex_mem = self._Latch.bubble_slot()
        self.mem_wb = self._Latch.bubble_slot()
        self.pipe_stalls = 0
        self.pipe_flushes = 0
        self.pipe_branches = 0
        self.pipe_predicted_taken = 0
        self.pipe_predicted_not_taken = 0
        self.pipe_predictions_correct = 0
        self.pipe_predictions_incorrect = 0
        self._pipe_active = False
        self._pipe_mem_stalled = False
        self._pipe_icache_stall_remaining = 0
        self._pipe_icache_stall_total = 0
        self._pipe_icache_pending = None
        self._pipe_dcache_stall_remaining = 0
        self._pipe_dcache_stall_total = 0
        self._pipe_dcache_pending = None
        self._pipe_next_fetch_id = 0
        self._pipe_fetch_trap = None
        self._pipe_fetch_trap_pc = None
        self.pipe_trace.clear()

    def pipeline_state(self) -> PipelineSnapshot:
        """Return a read-only copy of the live pipeline state for observers."""

        def latch_snapshot(latch: Latch) -> PipelineLatchSnapshot:
            mnemonic = None
            if not latch.bubble and latch.decoded is not None:
                mnemonic = latch.decoded.get("inst_name", "?")
            return PipelineLatchSnapshot(
                bubble=latch.bubble,
                fetch_id=latch.fetch_id,
                pc=latch.pc,
                mnemonic=mnemonic,
            )

        latches = (
            latch_snapshot(self.if_id),
            latch_snapshot(self.id_ex),
            latch_snapshot(self.ex_mem),
            latch_snapshot(self.mem_wb),
        )
        drained = (
            all(latch.bubble for latch in latches)
            and self._pipe_icache_pending is None
            and self._pipe_dcache_pending is None
            and self._pipe_fetch_trap is None
        )
        ebreak_pending = any(
            latch is not None
            and not latch.bubble
            and latch.decoded is not None
            and latch.decoded.get("inst_name") == "ebreak"
            for latch in (
                self.if_id, self.id_ex, self.ex_mem, self.mem_wb,
                self._pipe_icache_pending,
            )
        )
        fetch_latch = self._pipe_icache_pending
        fetch_pc = (
            fetch_latch.pc
            if fetch_latch is not None and not fetch_latch.bubble
            else None if self.if_id.bubble else self.if_id.pc
        )
        return PipelineSnapshot(
            fetch_pc=fetch_pc,
            if_id=latches[0],
            id_ex=latches[1],
            ex_mem=latches[2],
            mem_wb=latches[3],
            drained=drained,
            draining=(self.proc.halted or ebreak_pending) and not drained,
            mcycle=self.csr.read(0xB00),
            minstret=self.csr.read(0xB02),
            stalls=self.pipe_stalls,
            flushes=self.pipe_flushes,
            branch_prediction=BranchPredictionSnapshot(
                total=self.pipe_branches,
                predicted_taken=self.pipe_predicted_taken,
                predicted_not_taken=self.pipe_predicted_not_taken,
                correct=self.pipe_predictions_correct,
                incorrect=self.pipe_predictions_incorrect,
            ),
            trace=tuple(deepcopy(self.pipe_trace)),
        )

    def configure_cache(self, total_size: int, ways: int, block_size: int = 64, policy: str = "fifo") -> bool:
        """Rebuild both L1 caches; return whether the geometry changed."""
        if (
            total_size == self._cache_size
            and ways == self._cache_ways
            and block_size == self._cache_block_size
            and policy == self._cache_policy
        ):
            return False
        self._cache_size = total_size
        self._cache_ways = ways
        self._cache_block_size = block_size
        self._cache_policy = policy
        self.icache = Cache(self.mem, total_size, block_size, ways, policy)
        self.dcache = Cache(self.mem, total_size, block_size, ways, policy)
        self.history.clear()
        return True

    def configure_cache_stalls(
        self, icache_miss_stall: int, dcache_miss_stall: int
    ) -> None:
        """Set non-destructive cache penalties for the timing engines."""
        self.icache_miss_stall = max(0, int(icache_miss_stall))
        self.dcache_miss_stall = max(0, int(dcache_miss_stall))

    def configure_pipeline(
        self,
        forwarding: bool | None = None,
        branch_predict: str | None = None,
    ) -> None:
        """Apply non-destructive forwarding and prediction settings."""
        if forwarding is not None:
            self.forwarding = bool(forwarding)
        if branch_predict in ("nottaken", "taken"):
            self.branch_predict = branch_predict

    def is_real_miss(self, cache) -> bool:
        """Return whether the last access missed a fillable cache line."""
        la = cache.last_access
        return la is not None and (not la.hit) and (la.way != -1)

    def burn_stall(self, n: int) -> None:
        """Advance all clock-derived counters by ``n`` penalty clocks."""
        for _ in range(n):
            self.proc.cycle_count()
            self.csr.increment_cycle()
            if self.timer:
                self.timer.time_increment()

    def step(self) -> dict | None:
        if self.proc.halted or self.proc.cycles >= self.max_cycles:
            return None

        pc = self.proc.read_pc()
        # Interrupts are taken at the boundary before this instruction.
        if self.csr.check_pending_trap(
            self.proc, pc, before_exec=True,
            inst_size=self.proc.INSTRUCTION_SIZE,
        ):
            self.proc.cycle_count()
            if self.verbose_register:
                print(self.state(), file=sys.stderr)
            self.csr.increment_cycle()
            if self.timer:
                self.timer.time_increment()
            snapshot = {
                "pc": pc,
                "instruction": 0,
                "decoded": None,
                "inst_name": "trap",
                "cycles": self.proc.cycles,
                "stages": ["TRAP"],
                "commit_stage": "TRAP",
                "mc": True,
                "stall_info": None,
            }
            self.history.append(snapshot)
            return snapshot

        try:
            instruction, inst_size = self.icache.fetch_instruction(pc)
        except TrapException as e:
            self.proc.cycle_count()
            self.csr.trap_enter(self.proc, e.mcause, e.mtval, mepc=pc)
            self.csr.increment_cycle()
            if self.timer:
                self.timer.time_increment()
            snapshot = {
                "pc": pc,
                "instruction": 0,
                "decoded": None,
                "inst_name": "trap",
                "cycles": self.proc.cycles,
                "stages": ["TRAP"],
                "commit_stage": "TRAP",
                "mc": True,
                "stall_info": None,
            }
            self.history.append(snapshot)
            return snapshot

        decoded = (
            self.decoder.decoding(instruction)
            if inst_size == 4
            else self.decoder.decode_compressed(instruction)
        )
        decoded["_inst_size"] = inst_size
        inst_name = decoded["inst_name"]
        stages = ["IF", "ID"] if inst_name in _ILLEGAL_NAMES else self.stages_for(decoded)
        mc = MCInstr(
            pc=pc,
            instruction=instruction,
            inst_size=inst_size,
            decoded=decoded,
            stages=stages,
            stage_idx=0,
        )
        self.proc.cycle_count()

        try:
            if inst_name in _ILLEGAL_NAMES:
                raise illegal_instruction(instruction, pc)
            r = self.mc_compute(mc)
            mc.rd = r.rd
            mc.result = r.result
            mc.mem_op = r.mem_op
            mc.next_pc = r.next_pc
            mc.commit_stage = r.commit_stage
            mc.csr_write = r.csr_write
            mc.halt = r.halt
            mc.trap = r.trap
            if mc.halt and self.trace:
                print("[EBREAK -- halted]", file=sys.stderr)
            self.commit_atomic(mc)

        except TrapException as e:
            self.csr.trap_enter(self.proc, e.mcause, e.mtval, mepc=pc)
            mc.trap = e

        if self.mem.waiting_for_input:
            # Replay without double-counting this incomplete instruction.
            self.proc.cycles -= 1
            self.proc.set_pc(pc)
            self._waiting_for_input = True
            return None
        self._waiting_for_input = False

        if mc.trap is None and not self.proc.halted and mc.next_pc is None:
            self.proc.increment_pc(inst_size)

        if self.verbose_register:
            print(self.state(), file=sys.stderr)
        
        self.csr.increment_cycle()
        if self.timer:
            self.timer.time_increment()

        if not self.proc.halted and mc.trap is None:
            self.csr.increment_instret()


        snapshot = {
            "pc": pc,
            "instruction": instruction,
            "decoded": decoded,
            "inst_name": inst_name,
            "cycles": self.proc.cycles,
            "stages": list(mc.stages),
            "commit_stage": mc.commit_stage,
            "mc": True,
            "stall_info": None,
        }
        self.history.append(snapshot)

        if self.trace:
            self.print_trace(snapshot)

        return snapshot

    def run(self, max_cycles: int | None = None, delay: float = 0.01) -> None:
        limit = max_cycles if max_cycles is not None else self.max_cycles
        configured_limit = self.max_cycles
        self.max_cycles = limit
        try:
            while not self.proc.halted and self.proc.cycles < limit:
                cycles_before = self.proc.cycles
                self.step()
                if self._waiting_for_input or self.proc.cycles == cycles_before:
                    break
        finally:
            self.max_cycles = configured_limit

        if delay > 0:
            time.sleep(delay)

    def stages_for(self, decoded: dict) -> list[str]:
        """Return the instruction class's multi-cycle stage sequence."""
        name = decoded["inst_name"]
        t = decoded["inst_type"]
        opcode = decoded.get("opcode")

        # --- System / control-flow first (explicit names) ---
        if name == "ebreak":
            return ["IF", "ID", "EX"]          # halt at EX — 3 clocks
        if name == "ecall":
            return ["IF", "ID", "EX"]          # env-call trap at EX — 3 clocks
        if name == "mret":
            return ["IF", "ID", "EX", "WB"]    # CSR/PC restore at WB — 4 clocks
        if name in ("fence", "fence.i"):
            return ["IF", "ID"]                # decode-only no-op — 2 clocks
        # JAL / JALR: PC redirect at EX, link-register write at WB — 4 clocks.
        # (Uniform with every other register-writing instruction: the rd write
        # always lands at WB. The redirect still happens at EX so the next
        # fetch sees the target PC immediately.)
        if name == "jal" or (t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_JALR"]):
            return ["IF", "ID", "EX", "WB"]
        if t == "B-Type":
            return ["IF", "ID", "EX"]
        if t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_LOAD"]:
            return ["IF", "ID", "EX", "MEM", "WB"]
        if t == "S-Type":
            return ["IF", "ID", "EX", "MEM"]
        if t == "CSR-Type":
            return ["IF", "ID", "EX", "WB"]
        if t in ("R-Type", "U-Type"):
            return ["IF", "ID", "EX", "WB"]
        if t == "I-Type" and opcode in (
            INSTRUCTION_TYPE["OP_I_IMM"],
            INSTRUCTION_TYPE["OP_I_ENV"],
        ):
            return ["IF", "ID", "EX", "WB"]

        raise NotImplementedError(
            f"step_clk: instruction '{name}' ({t}, opcode=0x{opcode:07x}) not in scope. "
            f"Add it to stages_for() and a compute_* helper."
        )

    def mc_compute(self, mc: MCInstr) -> ComputeResult:
        """Compute one in-flight instruction without committing it."""
        d = mc.decoded
        t = d["inst_type"]
        name = d["inst_name"]
        opcode = d.get("opcode")

        if name == "ebreak":
            return compute_ebreak(d)
        if name == "ecall":
            return compute_ecall(d)
        if name == "mret":
            return compute_mret(d, self.csr)
        if name in ("fence", "fence.i"):
            return compute_fence(d)
        if name == "jal":
            return compute_jal(d, mc.pc, mc.inst_size)
        if t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_JALR"]:
            return compute_jalr(d, self.proc, mc.pc, mc.inst_size)
        if t == "B-Type":
            return compute_branch(d, self.proc, mc.pc)
        if t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_LOAD"]:
            return compute_load(d, self.proc)
        if t == "S-Type":
            return compute_store(d, self.proc)
        if t == "CSR-Type":
            return compute_csr(
                d,
                self.proc,
                self.csr,
                instruction=mc.instruction,
                pc=mc.pc,
            )
        if t == "U-Type":
            return compute_utype(d, self.proc, mc.pc)
        if t == "R-Type":
            return compute_rtype(d, self.proc)
        if t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_IMM"]:
            return compute_itype_imm(d, self.proc)
        raise NotImplementedError(f"step_clk EX: '{name}' ({t}) not in scope")

    def mc_commit(self, mc: MCInstr, stage: str) -> None:
        """Apply the architectural effects scheduled for one stage."""
        if stage == "EX":
            if mc.halt and mc.commit_stage == "EX":
                self.proc.set_pc(mc.pc)
                self.proc.halt()
            elif mc.trap is not None:
                self.csr.trap_enter(self.proc, mc.trap.mcause, mc.trap.mtval, mepc=mc.pc)
            elif (
                mc.next_pc is not None
                and not self.proc.halted
                and mc.csr_write is None
            ):
                self.proc.set_pc(mc.next_pc)

        elif stage == "MEM" and mc.mem_op is not None:
            op = mc.mem_op
            if op["kind"] == "load":
                self.mem.resume_input()
                n = op["name"]
                if n == "lb":
                    mc.result = self.dcache.read_byte(op["addr"], signed=True) & 0xFFFFFFFF
                elif n == "lh":
                    mc.result = self.dcache.read_halfword(op["addr"], signed=True) & 0xFFFFFFFF
                elif n == "lw":
                    mc.result = self.dcache.read_word(op["addr"]) & 0xFFFFFFFF
                elif n == "lbu":
                    mc.result = self.dcache.read_byte(op["addr"], signed=False) & 0xFFFFFFFF
                elif n == "lhu":
                    mc.result = self.dcache.read_halfword(op["addr"], signed=False) & 0xFFFFFFFF
                else:
                    raise NotImplementedError(f"step_clk MEM load: '{n}' not in scope")
            elif op["kind"] == "store":
                n = op["name"]
                val = op["val"] & 0xFFFFFFFF
                if n == "sb":
                    self.dcache.write_byte(op["addr"], val)
                elif n == "sh":
                    self.dcache.write_halfword(op["addr"], val)
                elif n == "sw":
                    self.dcache.write_word(op["addr"], val)
                else:
                    raise NotImplementedError(f"step_clk MEM store: '{n}' not in scope")

        elif stage == "WB" and mc.commit_stage == "WB":
            if mc.halt:
                self.proc.set_pc(mc.pc)
                self.proc.halt()
            if mc.csr_write is not None:
                self.csr.write(mc.csr_write[0], mc.csr_write[1])
            if mc.next_pc is not None and mc.csr_write is not None:
                if not self.proc.halted:
                    self.proc.set_pc(mc.next_pc)
            if mc.rd is not None:
                self.proc.write_register(mc.rd, mc.result)

    def commit_atomic(self, mc: MCInstr) -> None:
        """Commit EX, MEM, and WB effects within one oracle clock."""
        self.mc_commit(mc, "EX")
        self.mc_commit(mc, "MEM")
        if mc.mem_op and mc.mem_op["kind"] == "load" and self.mem.waiting_for_input:
            return
        self.mc_commit(mc, "WB")

    def step_clk(self) -> dict | None:
        """Advance one multi-cycle clock; return a snapshot on retirement."""
        if self.proc.halted or self.proc.cycles >= self.max_cycles:
            return None

        self.proc.cycle_count()
        self.csr.increment_cycle()
        if self.timer:
            self.timer.time_increment()

        if self._mc is None:
            pc = self.proc.read_pc()
            trap_taken = self.csr.check_pending_trap(
                self.proc, pc, before_exec=True, inst_size=self.proc.INSTRUCTION_SIZE
            )
            if trap_taken:
                snapshot = {
                    "pc": pc,
                    "instruction": 0,
                    "decoded": None,
                    "inst_name": "trap",
                    "cycles": self.proc.cycles,
                    "stages": ["TRAP"],
                    "commit_stage": "TRAP",
                    "mc": True,
                }
                self.history.append(snapshot)
                return snapshot

            try:
                instruction, inst_size = self.icache.fetch_instruction(pc)
            except TrapException as e:
                self.csr.trap_enter(self.proc, e.mcause, e.mtval, mepc=pc)
                snapshot = {
                    "pc": pc,
                    "instruction": 0,
                    "decoded": None,
                    "inst_name": "trap",
                    "cycles": self.proc.cycles,
                    "stages": ["TRAP"],
                    "commit_stage": "TRAP",
                    "mc": True,
                    "stall_info": None,
                }
                self.history.append(snapshot)
                return snapshot
            if inst_size == 4:
                decoded = self.decoder.decoding(instruction)
            else:
                decoded = self.decoder.decode_compressed(instruction)
            decoded["_inst_size"] = inst_size

            if decoded.get("inst_name") in _ILLEGAL_NAMES:
                stages = ["IF", "ID"]
            else:
                stages = self.stages_for(decoded)

            self._mc = MCInstr(
                pc=pc,
                instruction=instruction,
                inst_size=inst_size,
                decoded=decoded,
                stages=stages,
                stage_idx=0,
            )

        mc = self._mc
        stage = mc.stages[mc.stage_idx]

        if stage == "IF":
            if self.is_real_miss(self.icache) and self.icache_miss_stall > 0:
                self.burn_stall(self.icache_miss_stall)
                mc.stall_info = ("IF", self.icache_miss_stall)
            else:
                mc.stall_info = None

        elif stage == "ID":
            mc.stall_info = None
            if mc.decoded.get("inst_name") in _ILLEGAL_NAMES and mc.trap is None:
                mc.trap = illegal_instruction(mc.instruction, mc.pc)
                mc.commit_stage = "ID"
                self.csr.trap_enter(self.proc, mc.trap.mcause, mc.trap.mtval, mepc=mc.pc)

        elif stage == "EX":
            mc.stall_info = None
            r = self.mc_compute(mc)
            mc.rd = r.rd
            mc.result = r.result
            mc.mem_op = r.mem_op
            mc.next_pc = r.next_pc
            mc.commit_stage = r.commit_stage
            mc.csr_write = r.csr_write
            mc.halt = r.halt
            mc.trap = r.trap
            self.mc_commit(mc, "EX")

        elif stage == "MEM":
            try:
                self.mc_commit(mc, "MEM")
            except TrapException as e:
                self.csr.trap_enter(self.proc, e.mcause, e.mtval, mepc=mc.pc)
                self._mc = None
                return None
            if mc.mem_op and mc.mem_op["kind"] == "load" and self.mem.waiting_for_input:
                self._waiting_for_input = True
                return None
            self._waiting_for_input = False
            if self.is_real_miss(self.dcache) and self.dcache_miss_stall > 0:
                self.burn_stall(self.dcache_miss_stall)
                mc.stall_info = ("MEM", self.dcache_miss_stall)
            else:
                mc.stall_info = None

        elif stage == "WB":
            mc.stall_info = None
            self.mc_commit(mc, "WB")

        mc.stage_idx += 1

        if mc.stage_idx >= len(mc.stages):
            if (
                not self.proc.halted
                and mc.trap is None
                and mc.next_pc is None
            ):
                self.proc.set_pc((mc.pc + mc.inst_size) & 0xFFFFFFFF)
            if not self.proc.halted and mc.trap is None:
                self.csr.increment_instret()
            snapshot = {
                "pc": mc.pc,
                "instruction": mc.instruction,
                "decoded": mc.decoded,
                "inst_name": mc.decoded["inst_name"],
                "cycles": self.proc.cycles,
                "stages": list(mc.stages),
                "commit_stage": mc.commit_stage,
                "mc": True,
                "stall_info": mc.stall_info,
            }
            self.history.append(snapshot)
            self._mc = None
            return snapshot

        return None

    def latch_to_mc(self, l: "MCInstr") -> "MCInstr":
        """Adapt a pipeline latch to the shared commit carrier."""
        return MCInstr(
            pc=l.pc,
            instruction=l.instruction,
            inst_size=l.inst_size,
            decoded=l.decoded,
            stages=["IF", "ID", "EX", "MEM", "WB"],
            stage_idx=4,
            rd=l.rd,
            result=l.result,
            next_pc=l.next_pc,
            mem_op=l.mem_op,
            commit_stage=l.commit_stage,
            csr_write=l.csr_write,
            halt=l.halt,
            trap=l.trap,
        )

    def pipe_forward(self, reg_idx: int) -> int | None:
        """Return the newest forwarded value, or ``None`` for the register file."""
        if reg_idx == 0:
            return None
        exm = self.ex_mem
        if not exm.bubble and exm.rd == reg_idx and exm.rd is not None:
            if not (exm.mem_op is not None and exm.mem_op.get("kind") == "load"
                    and exm.result is None):
                return exm.result
        mwb = self.mem_wb
        if not mwb.bubble and mwb.rd == reg_idx and mwb.rd is not None:
            return mwb.result
        return None

    def pipe_operand_overrides(self, decoded: dict) -> dict:
        """Build optional forwarded operand overrides for EX."""
        if not self.forwarding:
            return {}
        overrides: dict = {}
        rs1 = decoded.get("rs1")
        rs2 = decoded.get("rs2")
        if rs1 is not None:
            v = self.pipe_forward(rs1)
            if v is not None:
                overrides["rs1_val"] = v & 0xFFFFFFFF
        if rs2 is not None:
            v = self.pipe_forward(rs2)
            if v is not None:
                overrides["rs2_val"] = v & 0xFFFFFFFF
        return overrides

    def pipe_load_use_stall_ex(self, ex_in, id_in) -> bool:
        """Return whether the IF/ID consumer must wait for an ID/EX load."""
        if ex_in.bubble or id_in.bubble:
            return False
        d_ex = ex_in.decoded
        d_id = id_in.decoded
        if d_ex is None or d_id is None:
            return False
        # Is ex_in a load? (loads are I-Type with the LOAD opcode.)
        t_ex = d_ex.get("inst_type")
        op_ex = d_ex.get("opcode")
        is_load = (t_ex == "I-Type" and op_ex == INSTRUCTION_TYPE["OP_I_LOAD"])
        if not is_load:
            return False
        load_rd = d_ex.get("rd")
        if load_rd is None or load_rd == 0:
            return False
        # Does id_in read load_rd as rs1 or rs2?
        if d_id.get("rs1") == load_rd or d_id.get("rs2") == load_rd:
            return True
        return False

    def pipe_raw_hazard_ex(self, ex_in, mem_in, wb_in) -> bool:
        """Detect an unresolved register RAW hazard without forwarding."""
        if ex_in.bubble or ex_in.decoded is None:
            return False
        rs1 = ex_in.decoded.get("rs1")
        rs2 = ex_in.decoded.get("rs2")
        readers = {r for r in (rs1, rs2) if r}
        if not readers:
            return False
        for lag in (mem_in, wb_in):
            if lag.bubble:
                continue
            rd = lag.rd
            if rd is not None and rd != 0 and rd in readers:
                return True
        return False

    def pipe_csr_hazard_ex(self, ex_in, mem_in, wb_in) -> bool:
        """Detect explicit or implicit CSR ordering hazards at EX."""
        if ex_in.bubble or ex_in.decoded is None:
            return False
        decoded = ex_in.decoded
        name = decoded.get("inst_name")
        if decoded.get("inst_type") == "CSR-Type":
            csr_addr = decoded.get("csr_addr")
            touched_csrs = {csr_addr} if csr_addr is not None else set()
        elif name == "ecall" or name in _ILLEGAL_NAMES:
            touched_csrs = {0x300, 0x305, 0x341, 0x342, 0x343}
        elif name == "mret":
            touched_csrs = {0x300, 0x341}
        else:
            return False
        for lag in (mem_in, wb_in):
            if (
                not lag.bubble
                and lag.csr_write is not None
                and lag.csr_write[0] in touched_csrs
            ):
                return True
        return False

    def pipe_interrupt_pending(self) -> bool:
        """Preview enabled machine interrupts without entering a trap."""
        mstatus = self.csr.read(0x300)
        if not ((mstatus >> 3) & 1):
            return False
        supported = sum(1 << bit for bit in INTERRUPT_PRIORITY)
        return bool(self.csr.read(0x304) & self.csr.read(0x344) & supported)

    def pipe_predict_target(self, pc: int, inst_size: int, decoded: dict) -> int | None:
        """Return IF's predicted successor under the active strategy."""
        fall_through = (pc + inst_size) & 0xFFFFFFFF
        if self.branch_predict != "taken":
            return fall_through
        t = decoded.get("inst_type")
        opcode = decoded.get("opcode")
        imm = decoded.get("imm", 0)
        if t == "B-Type":
            return (pc + imm) & 0xFFFFFFFF
        if t == "J-Type":
            return (pc + imm) & 0xFFFFFFFF
        if t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_JALR"]:
            rs1 = decoded.get("rs1")
            base = self.proc.read_register(rs1) if rs1 is not None else pc
            return (base + imm) & 0xFFFFFFFE & 0xFFFFFFFF
        return fall_through

    def pipe_is_misprediction(self, ex_in, actual_next_pc: int | None) -> bool:
        """Return whether EX resolved to a successor different from IF's."""
        if ex_in.bubble or ex_in.decoded is None:
            return False
        d = ex_in.decoded
        t = d.get("inst_type")
        opcode = d.get("opcode")
        is_control = (
            t == "B-Type" or t == "J-Type"
            or (t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_JALR"])
        )
        if not is_control:
            return False
        predicted = ex_in.predicted_next_pc
        if actual_next_pc is not None:
            return predicted != actual_next_pc
        fall_through = (ex_in.pc + ex_in.inst_size) & 0xFFFFFFFF
        return predicted != fall_through

    def pipe_actual_next_pc(self, ex_in, resolved_next_pc: int | None) -> int | None:
        """Return a control instruction's resolved target or fall-through."""
        if resolved_next_pc is not None:
            return resolved_next_pc
        return (ex_in.pc + ex_in.inst_size) & 0xFFFFFFFF

    def pipe_record_branch_prediction(
        self,
        ex_in: Latch,
        resolved_next_pc: int | None,
    ) -> None:
        """Count one resolved conditional branch prediction."""
        if ex_in.decoded is None or ex_in.decoded.get("inst_type") != "B-Type":
            return
        fall_through = (ex_in.pc + ex_in.inst_size) & 0xFFFFFFFF
        predicted = ex_in.predicted_next_pc
        actual = (
            resolved_next_pc
            if resolved_next_pc is not None
            else fall_through
        )
        self.pipe_branches += 1
        if predicted != fall_through:
            self.pipe_predicted_taken += 1
        else:
            self.pipe_predicted_not_taken += 1
        if predicted == actual:
            self.pipe_predictions_correct += 1
        else:
            self.pipe_predictions_incorrect += 1

    def copy_latch(self, src: Latch) -> Latch:
        """Copy a latch so output mutation cannot alias the input snapshot."""
        return self._Latch(
            bubble=src.bubble,
            fetch_id=src.fetch_id,
            pc=src.pc,
            instruction=src.instruction,
            inst_size=src.inst_size,
            decoded=src.decoded,
            rd=src.rd,
            result=src.result,
            mem_op=src.mem_op,
            next_pc=src.next_pc,
            commit_stage=src.commit_stage,
            csr_write=src.csr_write,
            halt=src.halt,
            trap=src.trap,
            predicted_next_pc=src.predicted_next_pc,
        )

    def pipe_do_mem(self, l) -> None:
        """Perform one EX/MEM D-cache access."""
        if l.mem_op is None:
            return
        op = l.mem_op
        if op["kind"] == "load":
            self.mem.resume_input()
            n = op["name"]
            if n == "lb":
                l.result = self.dcache.read_byte(op["addr"], signed=True) & 0xFFFFFFFF
            elif n == "lh":
                l.result = self.dcache.read_halfword(op["addr"], signed=True) & 0xFFFFFFFF
            elif n == "lw":
                l.result = self.dcache.read_word(op["addr"]) & 0xFFFFFFFF
            elif n == "lbu":
                l.result = self.dcache.read_byte(op["addr"], signed=False) & 0xFFFFFFFF
            elif n == "lhu":
                l.result = self.dcache.read_halfword(op["addr"], signed=False) & 0xFFFFFFFF
            else:
                raise NotImplementedError(f"step_pipe MEM load: '{n}' not in scope")
        elif op["kind"] == "store":
            n = op["name"]
            val = op["val"] & 0xFFFFFFFF
            if n == "sb":
                self.dcache.write_byte(op["addr"], val)
            elif n == "sh":
                self.dcache.write_halfword(op["addr"], val)
            elif n == "sw":
                self.dcache.write_word(op["addr"], val)
            else:
                raise NotImplementedError(f"step_pipe MEM store: '{n}' not in scope")

    def pipe_compute_with_forward(self, l) -> "ComputeResult":
        """Compute an EX instruction with optional forwarded operands."""
        d = l.decoded
        t = d["inst_type"]
        name = d["inst_name"]
        opcode = d.get("opcode")
        ov = self.pipe_operand_overrides(d)

        if name == "ebreak":
            return compute_ebreak(d)
        if name == "ecall":
            return compute_ecall(d)
        if name == "mret":
            return compute_mret(d, self.csr)
        if name in ("fence", "fence.i"):
            return compute_fence(d)
        if name == "jal":
            return compute_jal(d, l.pc, l.inst_size)
        if t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_JALR"]:
            return compute_jalr(d, self.proc, l.pc, l.inst_size, **ov)
        if t == "B-Type":
            return compute_branch(d, self.proc, l.pc, **ov)
        if t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_LOAD"]:
            return compute_load(d, self.proc, **ov)
        if t == "S-Type":
            return compute_store(d, self.proc, **ov)
        if t == "CSR-Type":
            return compute_csr(
                d,
                self.proc,
                self.csr,
                instruction=l.instruction,
                pc=l.pc,
                **ov,
            )
        if t == "U-Type":
            return compute_utype(d, self.proc, l.pc)
        if t == "R-Type":
            return compute_rtype(d, self.proc, **ov)
        if t == "I-Type" and opcode == INSTRUCTION_TYPE["OP_I_IMM"]:
            return compute_itype_imm(d, self.proc, **ov)
        raise NotImplementedError(f"step_pipe EX: '{name}' ({t}) not in scope")

    def step_pipe(self) -> dict | None:
        """Advance one pipeline clock; return a snapshot on WB retirement."""
        ebreak_pending = any(
            latch is not None
            and not latch.bubble
            and latch.decoded is not None
            and latch.decoded.get("inst_name") == "ebreak"
            for latch in (
                self.if_id, self.id_ex, self.ex_mem, self.mem_wb,
                self._pipe_icache_pending,
            )
        )
        # Halted pipelines must still drain older work.
        if (
            self.proc.cycles >= self.max_cycles
            and not self.proc.halted
            and not ebreak_pending
        ):
            return None

        self._pipe_active = True

        draining = self.proc.halted
        if draining:
            pipe_has_instr = (
                not self.if_id.bubble or not self.id_ex.bubble
                or not self.ex_mem.bubble or not self.mem_wb.bubble
                or self._pipe_icache_pending is not None
            )
            if not pipe_has_instr:
                return None

        wb_in = self.mem_wb
        mem_in = self.ex_mem
        ex_in = self.id_ex
        id_in = self.if_id
        ebreak_in_latches = any(
            not latch.bubble
            and latch.decoded is not None
            and latch.decoded.get("inst_name") == "ebreak"
            for latch in (id_in, ex_in, mem_in, wb_in)
        )

        if not draining:
            self.proc.cycle_count()
        self.csr.increment_cycle()
        if self.timer:
            self.timer.time_increment()

        mem_replay = self._pipe_mem_stalled
        dcache_replay = self._pipe_dcache_stall_remaining > 0
        dcache_freeze = self._pipe_dcache_stall_remaining > 1
        mem_blocked = mem_replay or dcache_freeze
        cache_stall_this_cycle = False
        cache_stall_stage: str | None = None
        cache_stall_index = 0
        cache_stall_total = 0
        cache_stall_latch: Latch | None = None
        if self.forwarding:
            load_use = (not mem_blocked) and self.pipe_load_use_stall_ex(ex_in, id_in)
            raw_block = False
        else:
            load_use = False
            raw_block = (not mem_blocked) and self.pipe_raw_hazard_ex(ex_in, mem_in, wb_in)
        csr_hazard = (not mem_blocked) and self.pipe_csr_hazard_ex(ex_in, mem_in, wb_in)
        stall = [False, False, False, False, False]
        if load_use:
            stall[S_ID] = True
        if csr_hazard or raw_block:
            stall[S_EX] = True
        retired_snapshot: dict | None = None
        wb_halt = not wb_in.bubble and wb_in.halt

        if not wb_in.bubble and wb_in.decoded is not None:
            mc = self.latch_to_mc(wb_in)
            self.mc_commit(mc, "WB")
            if mc.trap is None and not wb_in.halt:
                self.csr.increment_instret()
            retired_snapshot = {
                "fetch_id": wb_in.fetch_id,
                "pc": wb_in.pc,
                "instruction": wb_in.instruction,
                "decoded": wb_in.decoded,
                "inst_name": wb_in.decoded["inst_name"],
                "cycles": self.proc.cycles,
                "stages": ["IF", "ID", "EX", "MEM", "WB"],
                "commit_stage": wb_in.commit_stage,
                "mc": True,
                "pipe": True,
                "stall_info": None,
            }
            self.history.append(retired_snapshot)

        if wb_halt:
            self.pipe_flushes += sum(
                not latch.bubble for latch in (mem_in, ex_in, id_in)
            )
            if self._pipe_icache_pending is not None:
                self.pipe_flushes += 1

        mem_trap = False
        # A new input wait freezes EX immediately so it cannot replace EX/MEM.
        mem_freeze_now = False
        if wb_halt:
            new_mem_out = self._Latch.bubble_slot()
            new_ex_to_commit = None
            mem_replay = False
            self._pipe_mem_stalled = False
            self._pipe_dcache_stall_remaining = 0
            self._pipe_dcache_stall_total = 0
            self._pipe_dcache_pending = None
            self.resume_input()
        elif dcache_replay:
            # The completed cache access must not be issued again.
            self._pipe_dcache_stall_remaining -= 1
            if self._pipe_dcache_stall_remaining > 0:
                new_mem_out = self._Latch.bubble_slot()
                new_ex_to_commit = mem_in
                mem_freeze_now = True
                cache_stall_this_cycle = True
                cache_stall_stage = "MEM"
                cache_stall_total = self._pipe_dcache_stall_total
                cache_stall_index = (
                    cache_stall_total
                    - self._pipe_dcache_stall_remaining
                    + 1
                )
                cache_stall_latch = mem_in
                self.pipe_stalls += 1
            else:
                new_mem_out = self._pipe_dcache_pending
                new_ex_to_commit = None
                self._pipe_dcache_pending = None
                self._pipe_dcache_stall_total = 0
        elif mem_replay and self.mem.waiting_for_input:
            new_mem_out = self._Latch.bubble_slot()
            new_ex_to_commit = mem_in
            mem_freeze_now = True
        elif mem_replay:
            mem_replay = False
            new_mem_out = self.copy_latch(mem_in)
            new_ex_to_commit = None
            if not mem_in.bubble and mem_in.mem_op is not None:
                try:
                    self.pipe_do_mem(new_mem_out)
                except TrapException as e:
                    self.csr.trap_enter(self.proc, e.mcause, e.mtval, mepc=mem_in.pc)
                    new_mem_out = self._Latch.bubble_slot()
                    mem_trap = True
            self._pipe_mem_stalled = False
            self._waiting_for_input = False
        else:
            new_mem_out = self.copy_latch(mem_in)
            new_ex_to_commit = None
            if not mem_in.bubble and mem_in.mem_op is not None:
                try:
                    self.pipe_do_mem(new_mem_out)
                except TrapException as e:
                    self.csr.trap_enter(self.proc, e.mcause, e.mtval, mepc=mem_in.pc)
                    new_mem_out = self._Latch.bubble_slot()
                    mem_trap = True
            if (
                not mem_in.bubble and mem_in.mem_op is not None
                and mem_in.mem_op.get("kind") == "load"
                and self.mem.waiting_for_input
            ):
                self._pipe_mem_stalled = True
                self._waiting_for_input = True
                new_mem_out = self._Latch.bubble_slot()
                new_ex_to_commit = mem_in
                mem_freeze_now = True
            elif (
                not mem_trap
                and not mem_in.bubble
                and mem_in.mem_op is not None
                and self.is_real_miss(self.dcache)
                and self.dcache_miss_stall > 0
            ):
                self._pipe_dcache_stall_remaining = self.dcache_miss_stall
                self._pipe_dcache_stall_total = self.dcache_miss_stall
                self._pipe_dcache_pending = new_mem_out
                new_mem_out = self._Latch.bubble_slot()
                new_ex_to_commit = mem_in
                mem_freeze_now = True
                cache_stall_this_cycle = True
                cache_stall_stage = "MEM"
                cache_stall_index = 1
                cache_stall_total = self.dcache_miss_stall
                cache_stall_latch = mem_in
                self.pipe_stalls += 1
            else:
                self._pipe_mem_stalled = False
                self._waiting_for_input = False

        if mem_freeze_now or mem_replay:
            stall[S_MEM] = True
        # An older stalled stage freezes every younger stage.
        for s in (S_MEM, S_EX, S_ID, S_IF):
            if stall[s + 1]:
                stall[s] = True

        ex_redirect = False
        ex_trap = False
        if wb_halt:
            new_ex_out = self._Latch.bubble_slot()
        elif mem_trap:
            # Older MEM traps suppress irreversible younger EX effects.
            new_ex_out = self._Latch.bubble_slot()
        elif stall[S_EX] and (mem_replay or mem_freeze_now):
            new_ex_out = new_ex_to_commit if new_ex_to_commit is not None else mem_in
        elif stall[S_EX]:
            new_ex_out = self._Latch.bubble_slot()
            self.pipe_stalls += 1
        else:
            new_ex_out = self.copy_latch(ex_in)
            if not ex_in.bubble and ex_in.decoded is not None:
                d = ex_in.decoded
                if d.get("inst_name") in _ILLEGAL_NAMES:
                    new_ex_out.trap = illegal_instruction(ex_in.instruction, ex_in.pc)
                    new_ex_out.commit_stage = "ID"
                    self.csr.trap_enter(
                        self.proc, new_ex_out.trap.mcause, new_ex_out.trap.mtval,
                        mepc=ex_in.pc,
                    )
                    ex_trap = True
                else:
                    r = self.pipe_compute_with_forward(ex_in)
                    new_ex_out.rd = r.rd
                    new_ex_out.result = r.result
                    new_ex_out.mem_op = r.mem_op
                    new_ex_out.next_pc = r.next_pc
                    new_ex_out.commit_stage = (
                        "WB" if d.get("inst_name") == "ebreak"
                        else r.commit_stage
                    )
                    new_ex_out.csr_write = r.csr_write
                    new_ex_out.halt = r.halt
                    new_ex_out.trap = r.trap
                    speculative_pc = self.proc.read_pc()
                    self.mc_commit(self.latch_to_mc(new_ex_out), "EX")
                    self.pipe_record_branch_prediction(
                        ex_in,
                        new_ex_out.next_pc,
                    )
                    # MRET redirects now but keeps its ordered WB CSR write.
                    mret_redirect = (
                        d.get("inst_name") == "mret"
                        and new_ex_out.next_pc is not None
                        and not self.proc.halted
                    )
                    if mret_redirect:
                        self.proc.set_pc(new_ex_out.next_pc)
                        new_ex_out.next_pc = None
                    if new_ex_out.trap is not None and new_ex_out.commit_stage == "EX":
                        ex_trap = True
                    elif mret_redirect:
                        ex_redirect = True
                    elif (
                        new_ex_out.csr_write is None
                        and not self.proc.halted
                        and self.pipe_is_misprediction(ex_in, new_ex_out.next_pc)
                    ):
                        ex_redirect = True
                        actual = self.pipe_actual_next_pc(ex_in, new_ex_out.next_pc)
                        if actual is not None:
                            self.proc.set_pc(actual)
                    elif (
                        new_ex_out.next_pc is not None
                        and new_ex_out.csr_write is None
                        and not self.proc.halted
                    ):
                        # Keep IF's already-advanced position on a correct prediction.
                        self.proc.set_pc(speculative_pc)

        propagated_freeze = stall[S_ID] and (
            not load_use or mem_freeze_now or mem_replay
        )
        if wb_halt:
            new_ex_out = self._Latch.bubble_slot()
            new_id_out = self._Latch.bubble_slot()
            new_if_id_out = self._Latch.bubble_slot()
        elif propagated_freeze:
            new_id_out = ex_in
            new_if_id_out = id_in
        elif load_use:
            new_id_out = self._Latch.bubble_slot()
            new_if_id_out = id_in
            self.pipe_stalls += 1
        elif mem_trap:
            new_ex_out = self._Latch.bubble_slot()
            new_id_out = self._Latch.bubble_slot()
            new_if_id_out = id_in
            if not ex_in.bubble:
                self.pipe_flushes += 1
            if not id_in.bubble:
                self.pipe_flushes += 1
        elif ex_redirect or ex_trap:
            new_id_out = self._Latch.bubble_slot()
            new_if_id_out = id_in
            if not id_in.bubble:
                self.pipe_flushes += 1
        elif draining:
            new_id_out = self._Latch.bubble_slot()
            new_if_id_out = self._Latch.bubble_slot()
        else:
            new_id_out = self.copy_latch(id_in)
            new_if_id_out = id_in

        if wb_halt:
            new_if_id_out = self._Latch.bubble_slot()
            self._pipe_icache_stall_remaining = 0
            self._pipe_icache_stall_total = 0
            self._pipe_icache_pending = None
            self._pipe_fetch_trap = None
            self._pipe_fetch_trap_pc = None
        elif stall[S_IF] or draining:
            if draining:
                new_if_id_out = self._Latch.bubble_slot()
                self._pipe_icache_stall_remaining = 0
                self._pipe_icache_stall_total = 0
                self._pipe_icache_pending = None
        elif ex_redirect or ex_trap or mem_trap:
            if (ex_redirect or ex_trap) and not mem_trap:
                self.pipe_flushes += 1
            new_if_id_out = self._Latch.bubble_slot()
            self._pipe_icache_stall_remaining = 0
            self._pipe_icache_stall_total = 0
            self._pipe_icache_pending = None
            self._pipe_fetch_trap = None
            self._pipe_fetch_trap_pc = None
        elif ebreak_in_latches:
            new_if_id_out = self._Latch.bubble_slot()
            self._pipe_icache_stall_remaining = 0
            self._pipe_icache_stall_total = 0
            self._pipe_icache_pending = None
            self._pipe_fetch_trap = None
            self._pipe_fetch_trap_pc = None
        else:
            if self._pipe_icache_stall_remaining > 1:
                self._pipe_icache_stall_remaining -= 1
                new_if_id_out = self._Latch.bubble_slot()
                cache_stall_this_cycle = True
                cache_stall_stage = "IF"
                cache_stall_total = self._pipe_icache_stall_total
                cache_stall_index = (
                    cache_stall_total
                    - self._pipe_icache_stall_remaining
                    + 1
                )
                cache_stall_latch = self._pipe_icache_pending
                self.pipe_stalls += 1
            elif self._pipe_icache_stall_remaining == 1:
                self._pipe_icache_stall_remaining = 0
                new_if_id_out = self._pipe_icache_pending
                self._pipe_icache_stall_total = 0
                self._pipe_icache_pending = None
            else:
                # Gate IF until an enabled interrupt reaches a precise boundary.
                pipe_drained = (
                    new_id_out.bubble
                    and new_ex_out.bubble
                    and new_mem_out.bubble
                )
                fetch_trap_ready = (
                    id_in.bubble and ex_in.bubble
                    and mem_in.bubble and wb_in.bubble
                )
                interrupt_pending = self.pipe_interrupt_pending()
                trap_taken = False
                if (
                    fetch_trap_ready
                    and self._pipe_fetch_trap is not None
                    and self._pipe_fetch_trap_pc is not None
                    and not self.proc.halted
                ):
                    fault = self._pipe_fetch_trap
                    fault_pc = self._pipe_fetch_trap_pc
                    self._pipe_fetch_trap = None
                    self._pipe_fetch_trap_pc = None
                    self.csr.trap_enter(
                        self.proc, fault.mcause, fault.mtval, mepc=fault_pc
                    )
                    trap_taken = True
                elif (
                    pipe_drained
                    and self._pipe_fetch_trap is None
                    and interrupt_pending
                    and not self.proc.halted
                ):
                    pc = self.proc.read_pc()
                    trap_taken = self.csr.check_pending_trap(
                        self.proc, pc, before_exec=True,
                        inst_size=self.proc.INSTRUCTION_SIZE,
                    )
                if trap_taken:
                    new_if_id_out = self._Latch.bubble_slot()
                elif interrupt_pending or self._pipe_fetch_trap is not None:
                    new_if_id_out = self._Latch.bubble_slot()
                elif not self.proc.halted:
                    pc = self.proc.read_pc()
                    try:
                        instruction, inst_size = self.icache.fetch_instruction(pc)
                    except TrapException as e:
                        if fetch_trap_ready:
                            self.csr.trap_enter(
                                self.proc, e.mcause, e.mtval, mepc=pc
                            )
                        else:
                            self._pipe_fetch_trap = e
                            self._pipe_fetch_trap_pc = pc
                        new_if_id_out = self._Latch.bubble_slot()
                    else:
                        if inst_size == 4:
                            decoded = self.decoder.decoding(instruction)
                        else:
                            decoded = self.decoder.decode_compressed(instruction)
                        decoded["_inst_size"] = inst_size
                        predicted = self.pipe_predict_target(pc, inst_size, decoded)
                        new_if_id_out = self._Latch(
                            bubble=False, fetch_id=self._pipe_next_fetch_id,
                            pc=pc, instruction=instruction,
                            inst_size=inst_size, decoded=decoded,
                            predicted_next_pc=predicted,
                        )
                        self._pipe_next_fetch_id += 1
                        if self.proc.read_pc() == pc:
                            self.proc.set_pc(
                                predicted if predicted is not None
                                else (pc + inst_size) & 0xFFFFFFFF
                            )
                        if (
                            self.is_real_miss(self.icache)
                            and self.icache_miss_stall > 0
                        ):
                            self._pipe_icache_stall_remaining = self.icache_miss_stall
                            self._pipe_icache_stall_total = self.icache_miss_stall
                            self._pipe_icache_pending = new_if_id_out
                            cache_stall_stage = "IF"
                            cache_stall_index = 1
                            cache_stall_total = self.icache_miss_stall
                            cache_stall_latch = new_if_id_out
                            new_if_id_out = self._Latch.bubble_slot()
                            cache_stall_this_cycle = True
                            self.pipe_stalls += 1
                else:
                    new_if_id_out = self._Latch.bubble_slot()

        self.mem_wb = new_mem_out
        self.ex_mem = new_ex_out
        self.id_ex = new_id_out
        self.if_id = new_if_id_out

        def slot(l: Latch) -> dict | None:
            if l.bubble or l.decoded is None:
                return None
            return {
                "fetch_id": l.fetch_id,
                "pc": l.pc,
                "mnemonic": l.decoded.get("inst_name", "?"),
            }
        cache_stall = None
        if cache_stall_stage is not None and cache_stall_latch is not None:
            cache_stall = {
                "stage": cache_stall_stage,
                "index": cache_stall_index,
                "total": cache_stall_total,
                "slot": slot(cache_stall_latch),
            }
        self.pipe_trace.append({
            "cycle": self.csr.read(0xB00),
            "slots": {
                "IF/ID": slot(self.if_id),
                "ID/EX": slot(self.id_ex),
                "EX/MEM": slot(self.ex_mem),
                "MEM/WB": slot(self.mem_wb),
            },
            "stall": bool(
                stall[S_ID] or stall[S_EX] or stall[S_MEM]
                or cache_stall_this_cycle
            ),
            "hazard_stall_stage": (
                "ID" if load_use else "EX" if csr_hazard or raw_block else None
            ),
            "cache_stall": cache_stall,
            "flush": bool(wb_halt or ex_redirect or ex_trap or mem_trap),
            "retired": retired_snapshot["fetch_id"] if retired_snapshot is not None else None,
        })

        if self.trace and retired_snapshot is not None:
            self.print_trace(retired_snapshot)

        return retired_snapshot

    def state(self) -> str:
        return self.proc.description()

    def mem_dump(self, address: int | None = None, length: int = 256) -> str:
        addr = address if address is not None else self._entry_point
        return self.mem.description(addr, length=length)

    def csr_state(self) -> str:
        return self.csr.description()

    def cache_stats(self) -> dict:
        """Combined I-cache + D-cache statistics."""
        i = self.icache.get_stats()
        d = self.dcache.get_stats()
        total_acc = i["total_accesses"] + d["total_accesses"]
        total_hits = i["total_hits"] + d["total_hits"]
        total_miss = i["total_misses"] + d["total_misses"]
        return {
            "icache": i,
            "dcache": d,
            "total_accesses": total_acc,
            "total_hits": total_hits,
            "total_misses": total_miss,
            "hit_rate": (total_hits / total_acc * 100) if total_acc else 0.0,
        }

    def print_trace(self, snapshot: dict) -> None:
        pc = snapshot["pc"]
        inst_name = snapshot["inst_name"]
        decoded = snapshot["decoded"]
        rd = decoded.get("rd")
        changed = ""
        if rd is not None and rd != 0:
            val = self.proc.read_register(rd)
            changed = f"  x{rd}=0x{val:08x}"

        print(
            f"Cycle {self.proc.cycles:>4}  "
            f"PC=0x{pc:08x}  "
            f"{inst_name:<8}"
            f"{changed}",
            file=sys.stderr,
        )
