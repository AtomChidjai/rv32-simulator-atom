"""Five-stage pipeline timing and single-cycle state-parity tests."""

import pytest

from rv32i import Simulator
from rv32i.devices import (
    raise_external_irq,
    raise_software_irq,
    register_default_devices,
)


# ---- tiny assembler helpers (hand-built encodings, no toolchain) ----------
def encode_r(funct7, rs2, rs1, funct3, rd, opcode=0b0110011):
    return ((funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode) & 0xFFFFFFFF


def encode_i(imm, rs1, funct3, rd, opcode=0b0010011):
    return ((imm << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode) & 0xFFFFFFFF


def encode_s(imm, rs2, rs1, funct3):
    imm_hi = (imm >> 5) & 0x7F
    imm_lo = imm & 0x1F
    return ((imm_hi << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (imm_lo << 7) | 0b0100011) & 0xFFFFFFFF


def encode_u(imm31_12, rd, opcode):
    return ((imm31_12 << 12) | (rd << 7) | opcode) & 0xFFFFFFFF


def encode_b(imm, rs2, rs1, funct3):
    """B-Type immediate encoding. imm is the byte offset (must be even)."""
    imm &= 0x1FFE
    b12 = (imm >> 12) & 1
    b10_5 = (imm >> 5) & 0x3F
    b4_1 = (imm >> 1) & 0xF
    b11 = (imm >> 11) & 1
    return (
        (b12 << 31) | (b10_5 << 25) | (rs2 << 20) | (rs1 << 15)
        | (funct3 << 12) | (b4_1 << 8) | (b11 << 7) | 0b1100011
    ) & 0xFFFFFFFF


def encode_j(imm, rd):
    imm &= 0x1FFFFF
    b20 = (imm >> 20) & 1
    b10_1 = (imm >> 1) & 0x3FF
    b11 = (imm >> 11) & 1
    b19_12 = (imm >> 12) & 0xFF
    return ((b20 << 31) | (b10_1 << 21) | (b11 << 20) | (b19_12 << 12) | (rd << 7) | 0b1101111) & 0xFFFFFFFF


def encode_words(words):
    return b"".join(w.to_bytes(4, "little") for w in words)


EBREAK = 0x00100073


def make_simulator(words, max_cycles=2000):
    sim = Simulator(max_cycles=max_cycles)
    sim.mem.load_bytes(0, encode_words(words))
    sim.timer = register_default_devices(sim.mem, sim.csr)
    sim.proc.reset(pc=0)
    return sim


def run_pipe(sim):
    """Run the pipeline engine to halt/drain, collecting retirement snapshots."""
    snaps = []
    while True:
        if sim.proc.halted and sim.if_id.bubble and sim.id_ex.bubble \
                and sim.ex_mem.bubble and sim.mem_wb.bubble:
            break
        if not sim.proc.halted and sim.proc.cycles >= sim.max_cycles:
            break
        s = sim.step_pipe()
        if s is not None:
            snaps.append(s)
    return snaps


def run_sc(sim):
    """Run the single-cycle oracle to halt."""
    while not sim.proc.halted and sim.proc.cycles < sim.max_cycles:
        if sim.step() is None:
            break


def assert_state_parity(mc, sc, mem_words=None):
    """Assert two sims (pipeline + single-cycle) reach identical state."""
    assert mc.proc.registers == sc.proc.registers, "register file mismatch"
    assert mc.proc.read_pc() == sc.proc.read_pc(), "PC mismatch"
    if mem_words:
        for off in mem_words:
            a = mc.mem.read_word(off)
            b = sc.mem.read_word(off)
            assert a == b, f"mem[0x{off:08x}] mismatch: pipe=0x{a:08x} sc=0x{b:08x}"


def pipe_with_cache_stalls(words, *, ic=0, dc=0):
    sim = Simulator(
        max_cycles=2000,
        icache_miss_stall=ic,
        dcache_miss_stall=dc,
    )
    sim.mem.load_bytes(0, encode_words(words))
    sim.proc.reset(pc=0)
    return sim


# Straight-line execution

def test_pipe_straight_line_state_and_ipc():
    """A straight-line ALU program (no hazards) retires with IPC == 1.0 and
    matches the single-cycle oracle's architectural state exactly."""
    prog = [
        encode_i(5, 0, 0, 1),    # addi x1, x0, 5
        encode_i(7, 0, 0, 2),    # addi x2, x0, 7
        encode_r(0, 2, 1, 0, 3), # add  x3, x1, x2  = 12
        encode_r(1, 2, 1, 0, 4), # mul  x4, x1, x2  = 35  (funct7=1 ⇒ mul)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc)
    # Oracle values.
    assert pipe.proc.read_register(1) == 5
    assert pipe.proc.read_register(2) == 7
    assert pipe.proc.read_register(3) == 12
    assert pipe.proc.read_register(4) == 35
    # IPC: 4 real instructions retired; mcycle advances 1:1 in steady state
    # plus a few drain clocks. IPC should be ≤ 1.0 (stalls/flushes only lower
    # it) and bounded away from 0.
    minstret = pipe.csr.read(0xB02)
    mcycle = pipe.csr.read(0xB00)
    assert minstret == 4, f"expected 4 retired, got {minstret}"
    # No data hazards ⇒ no stalls; EBREAK gates fetch without a data stall.
    assert pipe.pipe_stalls == 0
    # IPC ≤ 1.0 (pipeline can't beat 1 instr/cycle single-issue).
    assert minstret / max(1, mcycle) <= 1.0


def test_pipe_ebreak_stops_younger_fetches_and_halts_at_wb():
    sim = make_simulator([
        encode_i(1, 0, 0, 1),
        EBREAK,
        encode_s(0, 3, 5, 2),
        encode_j(8, 0),
        encode_i(99, 0, 0, 2),
    ])
    sim.proc.write_register(3, 0xA5)
    sim.proc.write_register(5, 0x100)

    for _ in range(4):
        sim.step_pipe()

    assert not sim.proc.halted
    assert sim.ex_mem.halt
    assert sim.proc.read_register(1) == 0
    assert sim.id_ex.bubble
    assert sim.if_id.bubble
    assert sim._pipe_next_fetch_id == 2
    assert not sim.pipe_trace[-1]["flush"]
    assert sim.pipeline_state().draining

    older = sim.step_pipe()
    assert older is not None and older["inst_name"] == "addi"
    assert sim.proc.read_register(1) == 1
    assert not sim.proc.halted
    assert sim.mem_wb.halt
    assert sim.ex_mem.bubble
    assert sim.id_ex.bubble
    assert sim.if_id.bubble
    assert sim._pipe_next_fetch_id == 2
    assert sim.mem.read_word(0x100) == 0
    assert not sim.pipe_trace[-1]["flush"]

    breakpoint = sim.step_pipe()
    assert breakpoint is not None and breakpoint["inst_name"] == "ebreak"
    assert breakpoint["commit_stage"] == "WB"
    assert sim.proc.halted
    assert sim.proc.read_pc() == 4
    assert sim.mem.read_word(0x100) == 0
    assert sim.proc.read_register(2) == 0
    assert sim.pipe_trace[-1]["flush"]
    assert sim.pipe_flushes == 0
    assert all(
        slot is None or slot["pc"] < 8
        for entry in sim.pipe_trace
        for slot in entry["slots"].values()
    )
    assert sim.pipeline_state().drained


def test_pipe_trace_retains_every_clock_until_reset():
    sim = make_simulator([encode_j(0, 0)], max_cycles=300)

    for _ in range(300):
        sim.step_pipe()

    assert len(sim.pipe_trace) == 300
    assert sim.pipe_trace[0]["cycle"] == 1
    assert sim.pipe_trace[-1]["cycle"] == 300


def test_pipe_load_store_state_parity():
    """A load/store program matches the oracle. Loads do NOT trigger a load-
    use stall here (no consumer right behind them), so state is the only
    assertion."""
    prog = [
        encode_u(0x1, 5, 0b0110111),    # lui x5, 0x1   (x5 = 0x1000)
        encode_i(42, 0, 0, 3),          # addi x3, x0, 42
        encode_s(0, 3, 5, 2),           # sw  x3, 0(x5)
        encode_i(0, 5, 2, 4, 0b0000011),# lw  x4, 0(x5)  = 42
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc, mem_words=[0x1000])
    assert pipe.proc.read_register(4) == 42


# Hazards

def test_pipe_raw_dependency_forwarded_no_stall():
    """A back-to-back RAW dependency (producer then consumer) is absorbed by
    full forwarding — stall == 0, and the result is correct."""
    prog = [
        encode_i(10, 0, 0, 1),     # addi x1, x0, 10
        encode_r(0, 1, 1, 0, 2),   # add  x2, x1, x1  = 20  (reads x1 just written)
        encode_r(0, 2, 2, 0, 3),   # add  x3, x2, x2  = 40  (reads x2 just written)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc)
    assert pipe.proc.read_register(2) == 20
    assert pipe.proc.read_register(3) == 40
    assert pipe.pipe_stalls == 0, "RAW should be forwarded, not stalled"


def test_pipe_load_use_stall_one_bubble():
    """A load immediately followed by a consumer of its rd triggers exactly
    one load-use stall (the one unavoidable data stall under forwarding)."""
    prog = [
        encode_u(0x1, 5, 0b0110111),      # lui x5, 0x1
        encode_i(99, 0, 0, 3),            # addi x3, x0, 99
        encode_s(0, 3, 5, 2),             # sw  x3, 0(x5)
        encode_i(0, 5, 2, 1, 0b0000011),  # lw  x1, 0(x5)   = 99  (load)
        encode_r(0, 1, 1, 0, 2),          # add x2, x1, x1  = 198 (consumer, load-use)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc, mem_words=[0x1000])
    assert pipe.proc.read_register(1) == 99
    assert pipe.proc.read_register(2) == 198
    assert pipe.pipe_stalls == 1, f"expected 1 load-use stall, got {pipe.pipe_stalls}"


def test_pipe_load_use_trace_reports_id_stage_interlock():
    """The trace locates a forwarding load-use interlock in ID, not IF."""
    prog = [
        encode_u(0x1, 5, 0b0110111),      # lui x5, 0x1
        encode_i(99, 0, 0, 3),            # addi x3, x0, 99
        encode_s(0, 3, 5, 2),             # sw  x3, 0(x5)
        encode_i(0, 5, 2, 1, 0b0000011),  # lw  x1, 0(x5)
        encode_r(0, 1, 1, 0, 2),          # add x2, x1, x1
        EBREAK,
    ]
    sim = make_simulator(prog)
    run_pipe(sim)

    stall_index, stall_clock = next(
        (index, clock)
        for index, clock in enumerate(sim.pipe_trace)
        if clock.get("hazard_stall_stage") == "ID"
    )
    assert stall_clock["slots"]["IF/ID"]["pc"] == 16
    assert stall_clock["slots"]["ID/EX"] is None
    assert sim.pipe_trace[stall_index + 1]["slots"]["IF/ID"]["pc"] == 20


def test_pipe_load_use_no_consumer_no_stall():
    """A load NOT immediately followed by a consumer does NOT stall (the
    value catches up via forwarding by the time it's needed)."""
    prog = [
        encode_u(0x1, 5, 0b0110111),      # lui x5, 0x1
        encode_i(99, 0, 0, 3),            # addi x3, x0, 99
        encode_s(0, 3, 5, 2),             # sw  x3, 0(x5)
        encode_i(0, 5, 2, 1, 0b0000011),  # lw  x1, 0(x5)   = 99
        encode_i(7, 0, 0, 6),             # addi x6, x0, 7   (independent — no hazard)
        encode_r(0, 1, 6, 0, 2),          # add x2, x1, x6   = 106 (x1 ready by now)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc, mem_words=[0x1000])
    assert pipe.proc.read_register(2) == 106
    assert pipe.pipe_stalls == 0, "gap absorbs the load latency — no stall"


def encode_csr(csr_addr, rs1, funct3, rd):
    return ((csr_addr << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b1110011) & 0xFFFFFFFF


def test_pipe_csr_raw_hazard_stalls():
    """A CSR read immediately after a CSR write to the same CSR triggers a
    one-cycle stall: the write commits at WB, the read at EX would otherwise
    see the stale value. Surfaced by demo_all_types.c (csrrw then csrrs of
    mscratch). The pipeline must stall so the read sees the new value."""
    prog = [
        encode_i(10, 0, 0, 5),             # addi x5, x0, 10
        encode_csr(0x340, 5, 0b001, 6),    # csrrw x6, mscratch, x5  (mscratch = 10)
        encode_csr(0x340, 0, 0b010, 16),   # csrrs x16, mscratch, x0 (x16 = 10, reads new value)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc)
    assert pipe.proc.read_register(16) == 10, "CSR read must see the just-written value"
    assert pipe.csr.read(0x340) == 10
    assert pipe.pipe_stalls >= 1, f"CSR RAW should stall ≥1, got {pipe.pipe_stalls}"


def test_pipe_mret_waits_for_mepc_write_and_flushes_younger_instructions():
    """MRET implicitly reads mepc/mstatus and is an EX-stage redirect.

    A preceding mepc writer must commit before MRET reads it, and sequential
    instructions fetched behind MRET must never retire.
    """
    mret = 0x30200073
    nop = 0x00000013
    prog = [
        encode_i(0x20, 0, 0, 1),          # addi x1, x0, 0x20
        encode_csr(0x341, 1, 0b001, 0),   # csrrw x0, mepc, x1
        mret,
        encode_i(1, 0, 0, 2),             # wrong path
        encode_i(1, 0, 0, 4),             # wrong path
        nop,
        nop,
        nop,
        encode_i(3, 0, 0, 3),             # 0x20: return target
        EBREAK,
    ]
    pipe = Simulator(max_cycles=200, icache_miss_stall=2)
    pipe.mem.load_bytes(0, encode_words(prog))
    pipe.proc.reset(pc=0)
    pipe.csr.write(0x341, 0x18)      # stale target if the interlock fails

    sc = Simulator(max_cycles=200)
    sc.mem.load_bytes(0, encode_words(prog))
    sc.proc.reset(pc=0)
    sc.csr.write(0x341, 0x18)

    run_pipe(pipe)
    run_sc(sc)

    assert_state_parity(pipe, sc)
    assert pipe.proc.read_register(2) == 0
    assert pipe.proc.read_register(3) == 3
    assert pipe.proc.read_register(4) == 0
    assert all(s["pc"] not in (0x0C, 0x10) for s in pipe.history)
    assert pipe.pipe_stalls >= 1


def test_pipe_ecall_waits_for_implicit_trap_csr_dependencies():
    """ECALL must observe older mtvec writes and must not let an older mepc
    write overwrite the trap's own mepc value after trap entry."""
    nop = 0x00000013
    ecall = 0x00000073
    prog = [
        encode_i(0x20, 0, 0, 1),          # new mtvec
        encode_csr(0x305, 1, 0b001, 0),   # csrrw x0, mtvec, x1
        encode_i(0x40, 0, 0, 2),          # value that must not survive in mepc
        encode_csr(0x341, 2, 0b001, 0),   # csrrw x0, mepc, x2
        ecall,                       # mepc must become 0x10
        nop,
        nop,
        nop,
        encode_i(7, 0, 0, 7),             # 0x20: correct handler
        EBREAK,
        nop,
        nop,
        encode_i(3, 0, 0, 7),             # 0x30: stale-mtvec handler
        EBREAK,
    ]
    pipe = Simulator(max_cycles=300, icache_miss_stall=2)
    pipe.mem.load_bytes(0, encode_words(prog))
    pipe.proc.reset(pc=0)
    pipe.csr.write(0x305, 0x30)

    sc = Simulator(max_cycles=300)
    sc.mem.load_bytes(0, encode_words(prog))
    sc.proc.reset(pc=0)
    sc.csr.write(0x305, 0x30)

    run_pipe(pipe)
    run_sc(sc)

    assert_state_parity(pipe, sc)
    assert pipe.proc.read_register(7) == 7
    assert pipe.csr.read(0x341) == 0x10
    assert pipe.pipe_stalls >= 1


@pytest.mark.parametrize("branch_predict", ["nottaken", "taken"])
def test_pipe_enabled_interrupt_stops_fetch_and_drains_to_precise_boundary(branch_predict):
    """A continuously occupied pipeline must eventually take an enabled
    interrupt; waiting for it to become empty without stopping IF starves."""
    prog = [encode_j(0, 0)] + [0x00000013] * 7 + [
        encode_i(7, 0, 0, 7),             # 0x20: interrupt handler
        EBREAK,
    ]
    sim = Simulator(max_cycles=300, branch_predict=branch_predict)
    sim.mem.load_bytes(0, encode_words(prog))
    sim.proc.reset(pc=0)
    sim.csr.write(0x305, 0x20)       # mtvec
    sim.csr.write(0x304, 1 << 11)    # mie.MEIE
    sim.csr.write(0x300, 1 << 3)     # mstatus.MIE

    for _ in range(4):
        sim.step_pipe()
    raise_external_irq(sim.csr)
    run_pipe(sim)

    assert sim.proc.halted
    assert sim.proc.read_register(7) == 7
    assert len(sim.csr.trap_log) == 1
    assert sim.csr.trap_log[0]["cause"] == (1 << 31) | 11
    assert sim.proc.cycles < sim.max_cycles


@pytest.mark.parametrize(
    ("source", "irq_bit"),
    [("external", 11), ("software", 3), ("timer", 7)],
)
def test_pipe_interrupt_entry_shares_final_drain_wb_clock(source, irq_bit):
    """Trap entry shares the final in-flight instruction's WB clock."""
    prog = [
        encode_i(8, 0, 0, 1),             # value for mstatus.MIE
        encode_csr(0x300, 1, 0b010, 0),   # enable MIE at WB
        encode_i(0x22, 0, 0, 2),
        encode_i(0x33, 0, 0, 3),
        encode_i(0x44, 0, 0, 4),
        encode_i(0x55, 0, 0, 5),          # first not-fetched instruction
    ] + [0x00000013] * 10 + [EBREAK]
    sim = make_simulator(prog, max_cycles=80)
    sim.csr.write(0x305, 0x40)
    sim.csr.write(0x304, 1 << irq_bit)
    if source == "external":
        raise_external_irq(sim.csr)
    elif source == "software":
        raise_software_irq(sim.csr)
    else:
        sim.timer.mtimecmp = 1

    while not sim.csr.trap_log:
        sim.step_pipe()

    trap = sim.csr.trap_log[0]
    assert trap["cause"] == (1 << 31) | irq_bit
    assert trap["mepc"] == 0x14
    assert sim.history[-1]["pc"] == 0x10
    assert trap["cycle"] == sim.history[-1]["cycles"]
    assert [sim.proc.read_register(r) for r in (2, 3, 4, 5)] == [
        0x22, 0x33, 0x44, 0,
    ]


@pytest.mark.parametrize("source", ["external", "timer"])
def test_pipe_midflight_irq_drains_fetched_work_before_entry(source):
    """An IRQ arriving with all stages occupied gates IF and drains precisely."""
    prog = [
        encode_i(value, 0, 0, reg)
        for reg, value in enumerate(range(1, 6), start=1)
    ] + [0x00000013] * 11 + [EBREAK]
    sim = make_simulator(prog, max_cycles=80)
    sim.csr.write(0x305, 0x40)
    irq_bit = 11 if source == "external" else 7
    sim.csr.write(0x304, 1 << irq_bit)
    sim.csr.write(0x300, 1 << 3)

    for _ in range(4):
        sim.step_pipe()
    if source == "external":
        raise_external_irq(sim.csr)
    else:
        sim.timer.mtimecmp = sim.timer.mtime + 1

    while not sim.csr.trap_log:
        sim.step_pipe()

    trap = sim.csr.trap_log[0]
    assert trap["mepc"] == 0x10
    assert [snap["pc"] for snap in sim.history] == [0x00, 0x04, 0x08, 0x0C]
    assert trap["cycle"] == sim.history[-1]["cycles"]
    assert sim.proc.read_register(5) == 0


def test_pipe_interrupt_waits_for_dcache_miss_and_data_hazard_to_finish():
    """An IRQ arriving during a D-cache freeze stops future fetches without
    discarding the older miss or its dependent instruction."""
    prog = [
        encode_i(0x100, 0, 2, 1, 0b0000011),  # lw x1, 0x100(x0): cold miss
        encode_i(1, 1, 0, 2),                 # addi x2, x1, 1: load-use
        encode_j(0, 0),                       # keep pipeline occupied until IRQ gate
        0x00000013,
        0x00000013,
        0x00000013,
        0x00000013,
        0x00000013,
        encode_i(7, 0, 0, 7),                 # 0x20: interrupt handler
        EBREAK,
    ]
    sim = Simulator(max_cycles=300, dcache_miss_stall=3)
    sim.mem.load_bytes(0, encode_words(prog))
    sim.mem.write_word(0x100, 11)
    sim.proc.reset(pc=0)
    sim.csr.write(0x305, 0x20)
    sim.csr.write(0x304, 1 << 11)
    sim.csr.write(0x300, 1 << 3)

    for _ in range(4):
        sim.step_pipe()
    assert sim._pipe_dcache_stall_remaining > 0
    raise_external_irq(sim.csr)
    run_pipe(sim)

    assert sim.proc.halted
    assert sim.proc.read_register(1) == 11
    assert sim.proc.read_register(2) == 12
    assert sim.proc.read_register(7) == 7
    assert sim.pipe_stalls >= 4  # three miss clocks + load-use
    assert len(sim.csr.trap_log) == 1


def test_pipe_ignores_unsupported_pending_interrupt_bits():
    """The IF gate must use the same supported-interrupt mask as trap entry;
    otherwise an unknown mie/mip bit can stop fetch forever."""
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK], max_cycles=40)
    sim.csr.write(0x300, 1 << 3)  # mstatus.MIE
    sim.csr.write(0x304, 1 << 1)  # unsupported interrupt enable
    sim.csr.write(0x344, 1 << 1)  # unsupported interrupt pending

    run_pipe(sim)

    assert sim.proc.halted
    assert sim.proc.read_register(1) == 1
    assert sim.csr.trap_log == []


def test_pipe_mem_trap_suppresses_younger_ex_redirect():
    """A fault detected in MEM is older than the instruction in EX, so the
    younger control instruction must not overwrite the trap-handler PC."""
    nop = 0x00000013
    prog = [
        encode_i(2, 0, 2, 1, 0b0000011),  # misaligned lw x1, 2(x0)
        encode_j(0x2C, 0),                 # younger redirect to 0x30: must squash
        nop,
        nop,
        nop,
        nop,
        nop,
        nop,
        encode_i(7, 0, 0, 7),             # 0x20: trap handler
        EBREAK,
        nop,
        nop,
        encode_i(3, 0, 0, 7),             # 0x30: wrong redirect target
        EBREAK,
    ]
    pipe = make_simulator(prog)
    sc = make_simulator(prog)
    pipe.csr.write(0x305, 0x20)
    sc.csr.write(0x305, 0x20)

    run_pipe(pipe)
    run_sc(sc)

    assert_state_parity(pipe, sc)
    assert pipe.proc.read_register(7) == 7
    assert len(pipe.csr.trap_log) == 1


def test_pipe_taken_branch_flushes_two():
    """A taken branch resolves at EX; the two younger (wrong-path)
    instructions are flushed. The skipped instruction does NOT retire."""
    # beq x0, x0, +12  (always taken, skip the next 3 words to land on the
    # final addi). Wait — +12 skips 3 instructions. Let's skip 1 (the poison).
    prog = [
        encode_b(8, 0, 0, 0b000),   # beq x0, x0, +8   (taken: skip next instr)
        encode_i(666, 0, 0, 7),     # addi x7, x0, 666 (WRONG PATH — must not retire)
        encode_i(123, 0, 0, 1),     # addi x1, x0, 123 (branch target)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc)
    # The wrong-path instruction (x7=666) must NOT have retired.
    assert pipe.proc.read_register(7) == 0, "wrong-path instr leaked into x7"
    assert pipe.proc.read_register(1) == 123
    # A taken branch flushes its two younger stages; EBREAK fetches no younger
    # work and therefore adds no flushed slots.
    assert pipe.pipe_flushes >= 2, f"expected ≥2 flushes, got {pipe.pipe_flushes}"


def test_pipe_untaken_branch_no_flush():
    """An untaken branch does not flush — fall-through instructions retire."""
    # beq x0, x1, +8  (x0 != x1 ⇒ not taken). x1 is 0 by reset, but we set x1=1.
    prog = [
        encode_i(1, 0, 0, 1),       # addi x1, x0, 1
        encode_b(8, 0, 1, 0b000),   # beq x0, x1, +8  (0 != 1 ⇒ NOT taken)
        encode_i(55, 0, 0, 2),      # addi x2, x0, 55 (fall-through — must retire)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc)
    assert pipe.proc.read_register(2) == 55
    # There is no branch-driven flush, and EBREAK fetches no younger work.
    assert pipe.pipe_flushes == 0


def test_pipe_loop_many_taken_branches():
    """A small loop (many taken backward branches) matches the oracle and
    produces flushes proportional to the taken-branch count."""
    # Sum 1..4 using a loop (blt i, 5 loops while i < 5): x1 = accumulator,
    # x2 = counter, x3 = limit (5). Loop taken 4 times (i = 1,2,3,4).
    prog = [
        encode_i(0, 0, 0, 1),       # addi x1, x0, 0    (acc = 0)
        encode_i(1, 0, 0, 2),       # addi x2, x0, 1    (i = 1)
        encode_i(5, 0, 0, 3),       # addi x3, x0, 5    (limit = 5)
        # loop @ 0x0C:
        encode_r(0, 2, 1, 0, 1),    # add  x1, x1, x2
        encode_i(1, 2, 0, 2),       # addi x2, x2, 1
        encode_b(-8, 3, 2, 0b100),  # blt  x2, x3, -8  (back to loop if i < 5)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc)
    assert pipe.proc.read_register(1) == 10, "sum 1..4 (blt i,5) = 10"
    # Each taken branch flushes at least its fetched fall-through EBREAK. That
    # EBREAK gates IF, so a second wrong-path slot is not always present.
    assert pipe.pipe_flushes >= 4, f"expected ≥4 flushes, got {pipe.pipe_flushes}"


# ── Oracle parity across a diverse program (the headline check) ─────────

def test_pipe_oracle_diverse_program():
    """A program spanning U/R/I/load/store/jump types: step_pipe() and step()
    reach identical register file, PC, memory."""
    prog = [
        encode_u(0x1, 5, 0b0110111),               # lui x5, 0x1
        encode_i(12, 0, 0, 1),                     # addi x1, x0, 12
        encode_i(10, 0, 0, 2),                     # addi x2, x0, 10
        encode_r(0, 2, 1, 0, 3),                   # add  x3, x1, x2   = 22
        encode_r(1, 2, 1, 0, 4),                   # mul  x4, x1, x2   = 120
        encode_s(0, 3, 5, 2),                      # sw   x3, 0(x5)
        encode_i(0, 5, 2, 6, 0b0000011),           # lw   x6, 0(x5)    = 22
        encode_j(8, 7),                            # jal  x7, +8       (skip next)
        encode_i(666, 0, 0, 8),                    # addi x8, x0, 666  (skipped)
        encode_i(99, 0, 0, 9),                     # addi x9, x0, 99
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(pipe, sc, mem_words=[0x1000])
    assert pipe.proc.read_register(6) == 22
    assert pipe.proc.read_register(8) == 0   # wrong-path, skipped
    assert pipe.proc.read_register(9) == 99


# ── mcycle vs minstret divergence ───────────────────────────────────────

def test_pipe_mcycle_minstret_divergence_under_hazards():
    """Under hazards, mcycle > minstret by the stall + flush bubble count.
    A load-use stall adds exactly 1 stall cycle; the divergence reflects it."""
    # Load-use program: lw then add ⇒ 1 stall.
    prog = [
        encode_u(0x1, 5, 0b0110111),      # lui x5, 0x1
        encode_i(99, 0, 0, 3),            # addi x3, x0, 99
        encode_s(0, 3, 5, 2),             # sw  x3, 0(x5)
        encode_i(0, 5, 2, 1, 0b0000011),  # lw  x1, 0(x5)
        encode_r(0, 1, 1, 0, 2),          # add x2, x1, x1   (load-use stall)
        EBREAK,
    ]
    pipe = make_simulator(prog); run_pipe(pipe)
    minstret = pipe.csr.read(0xB02)
    mcycle = pipe.csr.read(0xB00)
    # The pipeline fills (4 clocks before the first retire) then drains. The
    # key invariant: mcycle > minstret (hazards add bubbles), and the gap is
    # at least the stall count.
    assert mcycle > minstret, "hazards should make mcycle exceed minstret"
    # The steady-state gap is (fill_depth - 1) + stalls + flushes. We only
    # assert the stalls contribute (gap ≥ stalls + a fill constant).
    assert (mcycle - minstret) >= pipe.pipe_stalls


# Forwarding-mode cases.

def make_configured_simulator(words, *, forwarding=True, branch_predict="nottaken", max_cycles=4000):
    """Like make_simulator() but configures pipeline hazard knobs."""
    sim = Simulator(max_cycles=max_cycles, forwarding=forwarding, branch_predict=branch_predict)
    sim.mem.load_bytes(0, encode_words(words))
    sim.timer = register_default_devices(sim.mem, sim.csr)
    sim.proc.reset(pc=0)
    return sim


def test_pipe_forwarding_off_stalls_raw():
    """A back-to-back ALU RAW dependency with forwarding OFF stalls the
    consumer (no EX/MEM→EX forward), yet reaches the correct result."""
    prog = [
        encode_i(10, 0, 0, 1),     # addi x1, x0, 10
        encode_r(0, 1, 1, 0, 2),   # add  x2, x1, x1  = 20  (reads x1 just written)
        encode_r(0, 2, 2, 0, 3),   # add  x3, x2, x2  = 40  (reads x2 just written)
        EBREAK,
    ]
    off = make_configured_simulator(prog, forwarding=False); run_pipe(off)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(off, sc)
    assert off.proc.read_register(2) == 20
    assert off.proc.read_register(3) == 40
    assert off.pipe_stalls > 0, "no-forwarding should stall on RAW"


def test_pipe_forwarding_off_load_stalls():
    """A load immediately followed by its consumer with forwarding OFF stalls
    (the load's value isn't available until WB). Result is still correct."""
    prog = [
        encode_u(0x1, 5, 0b0110111),      # lui x5, 0x1
        encode_i(99, 0, 0, 3),            # addi x3, x0, 99
        encode_s(0, 3, 5, 2),             # sw  x3, 0(x5)
        encode_i(0, 5, 2, 1, 0b0000011),  # lw  x1, 0(x5)   = 99
        encode_r(0, 1, 1, 0, 2),          # add x2, x1, x1  = 198 (consumer)
        EBREAK,
    ]
    off = make_configured_simulator(prog, forwarding=False); run_pipe(off)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(off, sc, mem_words=[0x1000])
    assert off.proc.read_register(2) == 198
    assert off.pipe_stalls > 0, "no-forwarding should stall the load consumer"


def test_pipe_forwarding_off_more_stalls_than_on():
    """The pedagogical invariant: the same program stalls more under
    no-forwarding than under full forwarding."""
    prog = [
        encode_i(10, 0, 0, 1),     # addi x1, x0, 10
        encode_r(0, 1, 1, 0, 2),   # add  x2, x1, x1   = 20   (RAW on x1)
        encode_r(0, 2, 2, 0, 3),   # add  x3, x2, x2   = 40   (RAW on x2)
        encode_r(0, 3, 3, 0, 4),   # add  x4, x3, x3   = 80   (RAW on x3)
        EBREAK,
    ]
    off = make_configured_simulator(prog, forwarding=False); run_pipe(off)
    on = make_configured_simulator(prog, forwarding=True);  run_pipe(on)
    assert_state_parity(off, on)
    assert off.pipe_stalls > on.pipe_stalls, (
        f"no-forwarding should stall more: off={off.pipe_stalls} on={on.pipe_stalls}"
    )
    # Under full forwarding this chain has no data stall (load-use only).
    assert on.pipe_stalls == 0


def test_pipe_forwarding_on_no_raw_stall():
    """Regression guard: with forwarding ON (default), a back-to-back ALU RAW
    chain is fully forwarded — zero stalls. (Existing behavior, pinned.)"""
    prog = [
        encode_i(10, 0, 0, 1),     # addi x1, x0, 10
        encode_r(0, 1, 1, 0, 2),   # add  x2, x1, x1   = 20
        encode_r(0, 2, 2, 0, 3),   # add  x3, x2, x2   = 40
        EBREAK,
    ]
    on = make_configured_simulator(prog, forwarding=True); run_pipe(on)
    assert on.pipe_stalls == 0
    assert on.proc.read_register(3) == 40


# Branch-prediction cases.

def test_pipe_predict_taken_taken_branch_no_flush():
    """A taken branch under predict-TAKEN: IF fetched the target up front, so
    the prediction is correct → no flush attributable to that branch. Contrast
    with predict-not-taken, where the same branch flushes ≥2."""
    prog = [
        encode_b(8, 0, 0, 0b000),   # beq x0, x0, +8   (always taken, skip next instr)
        encode_i(666, 0, 0, 7),     # addi x7, x0, 666 (WRONG PATH — must not retire)
        encode_i(123, 0, 0, 1),     # addi x1, x0, 123 (branch target)
        EBREAK,
    ]
    taken = make_configured_simulator(prog, branch_predict="taken"); run_pipe(taken)
    nottaken = make_configured_simulator(prog, branch_predict="nottaken"); run_pipe(nottaken)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(taken, sc)
    assert_state_parity(nottaken, sc)
    assert taken.proc.read_register(7) == 0   # wrong path never retired
    assert taken.proc.read_register(1) == 123
    # The headline tradeoff: predict-taken saves the flush on a taken branch.
    assert taken.pipe_flushes < nottaken.pipe_flushes, (
        f"predict-taken should flush less on a taken branch: "
        f"taken={taken.pipe_flushes} nottaken={nottaken.pipe_flushes}"
    )
    taken_stats = taken.pipeline_state().branch_prediction
    nottaken_stats = nottaken.pipeline_state().branch_prediction
    assert (
        taken_stats.total,
        taken_stats.predicted_taken,
        taken_stats.correct,
        taken_stats.incorrect,
    ) == (1, 1, 1, 0)
    assert (
        nottaken_stats.total,
        nottaken_stats.predicted_not_taken,
        nottaken_stats.correct,
        nottaken_stats.incorrect,
    ) == (1, 1, 0, 1)


def test_pipe_predict_taken_untaken_branch_flushes():
    """An untaken branch under predict-TAKEN: IF fetched the (wrong) target,
    so the fall-through was never fetched → misprediction → flush. State still
    matches the oracle; the fall-through instruction retires."""
    prog = [
        encode_i(1, 0, 0, 1),       # addi x1, x0, 1
        encode_b(8, 0, 1, 0b000),   # beq x0, x1, +8  (0 != 1 ⇒ NOT taken)
        encode_i(55, 0, 0, 2),      # addi x2, x0, 55 (fall-through — must retire)
        EBREAK,
    ]
    taken = make_configured_simulator(prog, branch_predict="taken"); run_pipe(taken)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(taken, sc)
    assert taken.proc.read_register(2) == 55   # fall-through retired
    # Predict-taken on a not-taken branch must flush (the wrong target was fetched).
    assert taken.pipe_flushes > 0, "predict-taken on untaken branch must flush"
    stats = taken.pipeline_state().branch_prediction
    assert (
        stats.total,
        stats.predicted_taken,
        stats.correct,
        stats.incorrect,
    ) == (1, 1, 0, 1)


def test_pipe_predict_nottaken_taken_branch_flushes():
    """Regression guard: predict-NOTTAKEN on a taken branch flushes ≥2 (the
    classic 2-bubble penalty). Pins the default behavior explicitly."""
    prog = [
        encode_b(8, 0, 0, 0b000),   # beq x0, x0, +8   (taken)
        encode_i(666, 0, 0, 7),     # wrong path
        encode_i(123, 0, 0, 1),     # target
        EBREAK,
    ]
    nt = make_configured_simulator(prog, branch_predict="nottaken"); run_pipe(nt)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(nt, sc)
    assert nt.proc.read_register(1) == 123
    assert nt.pipe_flushes >= 2, f"predict-nottaken taken branch: ≥2 flushes, got {nt.pipe_flushes}"
    stats = nt.pipeline_state().branch_prediction
    assert (
        stats.total,
        stats.predicted_not_taken,
        stats.correct,
        stats.incorrect,
    ) == (1, 1, 0, 1)


def test_pipe_loop_both_strategies_parity():
    """A loop (many taken backward branches) reaches identical architectural
    state under both strategies; only the flush counts differ. Predict-taken
    wins hard on a loop (every backward branch is correctly predicted)."""
    prog = [
        encode_i(0, 0, 0, 1),       # addi x1, x0, 0    (acc = 0)
        encode_i(1, 0, 0, 2),       # addi x2, x0, 1    (i = 1)
        encode_i(5, 0, 0, 3),       # addi x3, x0, 5    (limit = 5)
        # loop @ 0x0C:
        encode_r(0, 2, 1, 0, 1),    # add  x1, x1, x2
        encode_i(1, 2, 0, 2),       # addi x2, x2, 1
        encode_b(-8, 3, 2, 0b100),  # blt  x2, x3, -8  (back to loop if i < 5)
        EBREAK,
    ]
    taken = make_configured_simulator(prog, branch_predict="taken"); run_pipe(taken)
    nottaken = make_configured_simulator(prog, branch_predict="nottaken"); run_pipe(nottaken)
    sc = make_simulator(prog); run_sc(sc)
    assert_state_parity(taken, sc)
    assert_state_parity(nottaken, sc)
    assert taken.proc.read_register(1) == 10   # sum 1..4
    # 4 taken backward branches. Predict-taken nails all of them; predict-
    # not-taken eats ~2 flushes each. The gap is large and deterministic.
    assert taken.pipe_flushes < nottaken.pipe_flushes, (
        f"loop: predict-taken should flush far less: "
        f"taken={taken.pipe_flushes} nottaken={nottaken.pipe_flushes}"
    )
    for sim in (taken, nottaken):
        stats = sim.pipeline_state().branch_prediction
        assert stats.total == 4
        assert stats.correct + stats.incorrect == stats.total
        assert stats.predicted_taken + stats.predicted_not_taken == stats.total


def test_pipe_branch_prediction_stats_reset_and_ignore_jumps():
    prog = [
        encode_j(8, 1),
        encode_i(99, 0, 0, 2),
        encode_b(8, 0, 0, 0b000),
        encode_i(99, 0, 0, 3),
        EBREAK,
    ]
    sim = make_configured_simulator(prog, branch_predict="nottaken")
    run_pipe(sim)

    stats = sim.pipeline_state().branch_prediction
    assert stats.total == 1
    assert stats.incorrect == 1

    sim.reset(pc=0)
    stats = sim.pipeline_state().branch_prediction
    assert stats.total == 0
    assert stats.correct == 0
    assert stats.incorrect == 0


# ── Cache-miss penalties ────────────────────────────────────────────────

def test_pipe_icache_miss_adds_configured_stall_clocks():
    """A cold IF miss delays the fetched instruction by exactly N clocks."""
    prog = [encode_i(7, 0, 0, 1), encode_i(9, 0, 0, 2), EBREAK]
    baseline = pipe_with_cache_stalls(prog)
    delayed = pipe_with_cache_stalls(prog, ic=3)

    run_pipe(baseline)
    run_pipe(delayed)

    assert_state_parity(delayed, baseline)
    assert delayed.csr.read(0xB00) == baseline.csr.read(0xB00) + 3
    assert delayed.pipe_stalls == baseline.pipe_stalls + 3
    assert delayed.icache.total_accesses == baseline.icache.total_accesses
    assert delayed.icache.total_misses == 1


def test_pipe_dcache_miss_adds_configured_stall_clocks_without_replay():
    """A cold MEM miss freezes younger stages for N clocks without issuing
    the cache request more than once."""
    prog = [
        encode_i(0x100, 0, 2, 1, 0b0000011),  # lw x1, 0x100(x0)
        encode_i(5, 0, 0, 2),                  # younger independent instruction
        EBREAK,
    ]
    baseline = pipe_with_cache_stalls(prog)
    delayed = pipe_with_cache_stalls(prog, dc=4)
    baseline.mem.write_word(0x100, 0x12345678)
    delayed.mem.write_word(0x100, 0x12345678)

    run_pipe(baseline)
    run_pipe(delayed)

    assert_state_parity(delayed, baseline)
    assert delayed.proc.read_register(1) == 0x12345678
    assert delayed.proc.read_register(2) == 5
    assert delayed.csr.read(0xB00) == baseline.csr.read(0xB00) + 4
    assert delayed.pipe_stalls == baseline.pipe_stalls + 4
    assert delayed.dcache.total_accesses == 1
    assert delayed.dcache.total_misses == 1


def test_pipe_dcache_hit_has_no_miss_penalty():
    """Only the first access to a cache line pays the configured penalty."""
    prog = [
        encode_i(0x100, 0, 2, 1, 0b0000011),  # lw x1, 0x100(x0): miss
        encode_i(0x104, 0, 2, 2, 0b0000011),  # lw x2, 0x104(x0): same-line hit
        EBREAK,
    ]
    baseline = pipe_with_cache_stalls(prog)
    delayed = pipe_with_cache_stalls(prog, dc=2)
    for sim in (baseline, delayed):
        sim.mem.write_word(0x100, 11)
        sim.mem.write_word(0x104, 22)

    run_pipe(baseline)
    run_pipe(delayed)

    assert_state_parity(delayed, baseline)
    assert delayed.csr.read(0xB00) == baseline.csr.read(0xB00) + 2
    assert delayed.dcache.total_accesses == 2
    assert delayed.dcache.total_misses == 1
    assert delayed.dcache.total_hits == 1


def test_pipe_dcache_store_miss_is_not_replayed():
    """A stalled write-through store is committed and counted only once."""
    prog = [
        encode_i(0x55, 0, 0, 1),  # addi x1, x0, 0x55
        encode_s(0x100, 1, 0, 2), # sw x1, 0x100(x0)
        EBREAK,
    ]
    sim = pipe_with_cache_stalls(prog, dc=3)

    run_pipe(sim)

    assert sim.mem.read_word(0x100) == 0x55
    assert sim.dcache.total_accesses == 1
    assert sim.dcache.total_misses == 1
    assert sim.pipe_stalls == 3


def test_pipe_dcache_miss_preserves_overlapping_load_use_hazard():
    """A fresh MEM freeze must not discard a younger load in EX when its
    consumer simultaneously raises the normal load-use interlock."""
    prog = [
        encode_i(0x100, 0, 2, 1, 0b0000011),  # older miss
        encode_i(0x104, 0, 2, 2, 0b0000011),  # younger load in EX on miss clock
        encode_r(0, 2, 2, 0, 3),              # load-use consumer in ID
        EBREAK,
    ]
    sim = pipe_with_cache_stalls(prog, dc=3)
    sim.mem.write_word(0x100, 11)
    sim.mem.write_word(0x104, 22)

    run_pipe(sim)

    assert sim.proc.read_register(1) == 11
    assert sim.proc.read_register(2) == 22
    assert sim.proc.read_register(3) == 44
    assert sim.pipe_stalls == 4  # 3 cache clocks + 1 load-use clock


def test_pipe_reset_drops_in_flight_cache_stalls():
    """Reset clears pending cache responses along with the pipeline latches."""
    sim = pipe_with_cache_stalls([encode_i(1, 0, 0, 1), EBREAK], ic=3)

    sim.step_pipe()
    assert sim.pipe_stalls == 1
    assert not sim.pipeline_state().drained

    sim.reset(pc=0)

    assert sim.pipe_stalls == 0
    assert sim.pipeline_state().drained
    assert sim._pipe_icache_stall_remaining == 0
    assert sim._pipe_dcache_stall_remaining == 0


def test_pipe_icache_miss_trace_matches_four_instruction_schedule():
    """Inst 2 occupies IF for the base clock plus two penalty clocks while
    Inst 1 continues and later instructions have not entered the pipeline."""
    nop = 0x00000013
    sim = Simulator(max_cycles=100, icache_miss_stall=2)
    sim.mem.load_bytes(60, encode_words([nop, nop, nop, nop, EBREAK]))
    sim.proc.reset(pc=60)
    sim.icache.fetch_instruction(60)  # Inst 1 hits; Inst 2 crosses into a cold line.

    run_pipe(sim)

    stalls = [t["cache_stall"] for t in sim.pipe_trace if t.get("cache_stall")]
    assert [
        (s["stage"], s["index"], s["total"], s["slot"]["pc"])
        for s in stalls
    ] == [
        ("IF", 1, 2, 64),
        ("IF", 2, 2, 64),
    ]
    assert sim.pipe_trace[1]["slots"]["ID/EX"]["pc"] == 60
    assert sim.pipe_trace[2]["slots"]["EX/MEM"]["pc"] == 60
    assert sim.pipe_trace[3]["slots"]["IF/ID"]["pc"] == 64


def test_pipe_dcache_miss_trace_matches_four_instruction_schedule():
    """Inst 2 occupies MEM for two penalty clocks while Inst 3 and Inst 4
    remain frozen at the inputs to EX and ID, respectively."""
    nop = 0x00000013
    sim = Simulator(max_cycles=100, dcache_miss_stall=2)
    sim.mem.load_bytes(0, encode_words([
        nop,                         # Inst 1
        encode_s(0, 9, 5, 2),             # Inst 2: sw x9, 0(x5)
        nop,                         # Inst 3
        nop,                         # Inst 4
        EBREAK,
    ]))
    sim.proc.reset(pc=0)
    sim.proc.write_register(5, 0x1000)

    run_pipe(sim)

    stall_clocks = [t for t in sim.pipe_trace if t.get("cache_stall")]
    assert [
        (t["cache_stall"]["stage"], t["cache_stall"]["index"])
        for t in stall_clocks
    ] == [("MEM", 1), ("MEM", 2)]
    for t in stall_clocks:
        assert t["cache_stall"]["total"] == 2
        assert t["cache_stall"]["slot"]["pc"] == 4
        assert t["slots"]["EX/MEM"]["pc"] == 4
        assert t["slots"]["ID/EX"]["pc"] == 8
        assert t["slots"]["IF/ID"]["pc"] == 12
    assert sim.pipe_stalls == 2
