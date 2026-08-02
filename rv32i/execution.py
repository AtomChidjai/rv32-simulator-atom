"""Instruction semantics shared by all execution engines."""

import os
import sys
from dataclasses import dataclass
from .cpu import Processor
from .memory import Memory
from .csr import CSRFile

DEBUG = os.environ.get("RV32I_DEBUG", "") not in ("", "0", "false")


def dbg(msg: str) -> None:
    if DEBUG:
        print(msg, file=sys.stderr)

def execute_instruction_rtype(decoded: dict, proc: Processor):
    """Compute and commit an R/M instruction."""
    if decoded["inst_type"] != "R-Type":
        return
    dbg(f"{decoded['inst_name']} is being executed.")
    r = compute_rtype(decoded, proc)
    proc.write_register(decoded["rd"], r.result & 0xFFFFFFFF)


def execute_instruction_itype_imm(decoded: dict, proc: Processor):
    """Compute and commit an immediate ALU instruction."""
    if decoded["inst_type"] != "I-Type":
        return
    dbg(f"{decoded['inst_name']} is being executed.")
    r = compute_itype_imm(decoded, proc)
    proc.write_register(decoded["rd"], r.result & 0xFFFFFFFF)


def execute_instruction_itype_load(decoded: dict, proc: Processor, mem):
    """Compute and commit a load unless input is unavailable."""
    if decoded["inst_type"] != "I-Type":
        return
    dbg(f"{decoded['inst_name']} is being executed.")
    r = compute_load(decoded, proc)
    op = r.mem_op
    addr = op["addr"]
    mem.resume_input()
    n = op["name"]
    if n == "lb":
        result = mem.read_byte(addr, signed=True)
    elif n == "lh":
        result = mem.read_halfword(addr, signed=True)
    elif n == "lw":
        result = mem.read_word(addr)
    elif n == "lbu":
        result = mem.read_byte(addr, signed=False)
    elif n == "lhu":
        result = mem.read_halfword(addr, signed=False)
    else:
        raise NotImplementedError(f"itype_load: '{n}' not in scope")
    if mem.waiting_for_input:
        return
    proc.write_register(decoded["rd"], result & 0xFFFFFFFF)


def execute_instruction_stype(decoded: dict, proc: Processor, mem):
    """Compute and commit a store."""
    if decoded["inst_type"] != "S-Type":
        return
    dbg(f"addr: 0x{(proc.read_register(decoded['rs1']) + decoded['imm']):08x}")
    dbg(f"{decoded['inst_name']} is being executed.")
    r = compute_store(decoded, proc)
    op = r.mem_op
    addr = op["addr"]
    val = op["val"] & 0xFFFFFFFF
    n = op["name"]
    if n == "sb":
        mem.write_byte(addr, val)
    elif n == "sh":
        mem.write_halfword(addr, val)
    elif n == "sw":
        mem.write_word(addr, val)
    else:
        raise NotImplementedError(f"stype: '{n}' not in scope")


def execute_instruction_btype(decoded: dict, proc: Processor, pc: int):
    """Resolve and commit a branch."""
    if decoded["inst_type"] != "B-Type":
        return
    dbg(f"{decoded['inst_name']} is being executed.")
    r = compute_branch(decoded, proc, pc)
    if r.next_pc is not None:
        dbg(f"pc: 0x{pc:08x}, imm: 0x{decoded['imm']:08x} jump to 0x{r.next_pc:08x}")
        proc.set_pc(r.next_pc)


def execute_instruction_utype(decoded: dict, proc: Processor):
    """Compute and commit a U-type instruction."""
    if decoded["inst_type"] != "U-Type":
        return
    dbg(f"{decoded['inst_name']} is being executed.")
    r = compute_utype(decoded, proc, proc.read_pc())
    proc.write_register(decoded["rd"], r.result & 0xFFFFFFFF)


def execute_instruction_jtype(decoded: dict, proc: Processor, pc: int):
    """Compute and commit JAL."""
    if decoded["inst_type"] != "J-Type":
        return
    dbg(f"{decoded['inst_name']} is being executed.")
    r = compute_jal(decoded, pc, decoded.get("_inst_size", 4))
    proc.write_register(decoded["rd"], r.result & 0xFFFFFFFF)
    proc.set_pc(r.next_pc)


def execute_instruction_itype_jalr(decoded: dict, proc: Processor):
    """Compute and commit JALR."""
    if decoded["inst_type"] != "I-Type":
        return
    dbg(f"{decoded['inst_name']} is being executed.")
    r = compute_jalr(decoded, proc, proc.read_pc(), decoded.get("_inst_size", 4))
    proc.write_register(decoded["rd"], r.result & 0xFFFFFFFF)
    proc.set_pc(r.next_pc)


def execute_instruction_csr(decoded: dict, proc: Processor, csr: CSRFile):
    """Compute and commit a CSR read/modify instruction."""
    if decoded["inst_type"] != "CSR-Type":
        return
    name = decoded["inst_name"]
    rd = decoded["rd"]
    rs1 = decoded["rs1"]
    csr_addr = decoded["csr_addr"]
    dbg(f"{name} is being executed.")
    r = compute_csr(decoded, proc, csr)
    if r.trap is not None:
        return
    if r.csr_write is not None:
        csr.write(r.csr_write[0], r.csr_write[1])
    if rd != 0:
        proc.write_register(rd, r.result & 0xFFFFFFFF)
    dbg(
        f"{name} csr=0x{csr_addr:03x}, rd=x{rd}, rs1=x{rs1} | "
        f"old=0x{r.result:08x} -> rd=0x{r.result:08x}"
    )

@dataclass
class ComputeResult:
    """Uncommitted result shared by all execution engines."""
    rd: int | None = None
    result: int | None = None
    mem_op: dict | None = None
    next_pc: int | None = None
    commit_stage: str = "WB"
    csr_write: tuple[int, int] | None = None
    halt: bool = False
    trap: object | None = None


def compute_rtype(
    decoded: dict,
    proc: Processor,
    rs1_val: int | None = None,
    rs2_val: int | None = None,
) -> ComputeResult:
    """Compute an R/M result for WB, with optional forwarded operands."""
    name = decoded["inst_name"]
    rd = decoded["rd"]
    if rs1_val is None:
        rs1_val = proc.read_register(decoded["rs1"])
    if rs2_val is None:
        rs2_val = proc.read_register(decoded["rs2"])

    if name == "add":
        result = rs1_val + rs2_val
    elif name == "sub":
        result = rs1_val - rs2_val
    elif name == "xor":
        result = rs1_val ^ rs2_val
    elif name == "or":
        result = rs1_val | rs2_val
    elif name == "and":
        result = rs1_val & rs2_val
    elif name == "sll":
        result = rs1_val << (rs2_val & 0x1F)
    elif name == "srl":
        result = rs1_val >> (rs2_val & 0x1F)
    elif name == "sra":
        result = Memory.sign_extend(rs1_val, 32) >> (rs2_val & 0x1F)
    elif name == "slt":
        result = 1 if Memory.sign_extend(rs1_val, 32) < Memory.sign_extend(rs2_val, 32) else 0
    elif name == "sltu":
        result = 1 if rs1_val < rs2_val else 0
    elif name == "mul":
        result = (rs1_val * rs2_val) & 0xFFFFFFFF
    elif name == "mulh":
        result = ((Memory.sign_extend(rs1_val, 32) * Memory.sign_extend(rs2_val, 32)) >> 32) & 0xFFFFFFFF
    elif name == "mulhsu":
        result = ((Memory.sign_extend(rs1_val, 32) * rs2_val) >> 32) & 0xFFFFFFFF
    elif name == "mulhu":
        result = ((rs1_val * rs2_val) >> 32) & 0xFFFFFFFF
    elif name == "div":
        s1 = Memory.sign_extend(rs1_val, 32)
        s2 = Memory.sign_extend(rs2_val, 32)
        if s2 == 0:
            result = 0xFFFFFFFF
        elif s1 == -0x80000000 and s2 == -1:
            result = 0x80000000
        else:
            sign = -1 if (s1 < 0) ^ (s2 < 0) else 1
            result = (sign * (abs(s1) // abs(s2))) & 0xFFFFFFFF
    elif name == "divu":
        result = 0xFFFFFFFF if rs2_val == 0 else (rs1_val // rs2_val) & 0xFFFFFFFF
    elif name == "rem":
        s1 = Memory.sign_extend(rs1_val, 32)
        s2 = Memory.sign_extend(rs2_val, 32)
        if s2 == 0:
            result = rs1_val
        elif s1 == -0x80000000 and s2 == -1:
            result = 0
        else:
            q = (abs(s1) // abs(s2))
            if (s1 < 0) ^ (s2 < 0):
                q = -q
            result = (s1 - q * s2) & 0xFFFFFFFF
    elif name == "remu":
        result = rs1_val if rs2_val == 0 else (rs1_val % rs2_val) & 0xFFFFFFFF
    else:
        raise NotImplementedError(f"compute_rtype: '{name}' not in scope")

    return ComputeResult(rd=rd, result=result & 0xFFFFFFFF, commit_stage="WB")


def compute_itype_imm(
    decoded: dict,
    proc: Processor,
    rs1_val: int | None = None,
) -> ComputeResult:
    """Compute an immediate ALU result for WB."""
    name = decoded["inst_name"]
    rd = decoded["rd"]
    if rs1_val is None:
        rs1_val = proc.read_register(decoded["rs1"])
    imm = Memory.sign_extend(decoded["imm"], 12)

    if name in ("addi", "nop"):
        result = rs1_val + imm
    elif name == "xori":
        result = rs1_val ^ imm
    elif name == "ori":
        result = rs1_val | imm
    elif name == "andi":
        result = rs1_val & imm
    elif name == "slli":
        result = rs1_val << (decoded["imm"] & 0x1F)
    elif name == "srli":
        result = rs1_val >> (decoded["imm"] & 0x1F)
    elif name == "srai":
        result = Memory.sign_extend(rs1_val, 32) >> (decoded["imm"] & 0x1F)
    elif name == "slti":
        result = 1 if Memory.sign_extend(rs1_val, 32) < Memory.sign_extend(imm, 12) else 0
    elif name == "sltiu":
        result = 1 if rs1_val < (imm & 0xFFFFFFFF) else 0
    else:
        raise NotImplementedError(f"compute_itype_imm: '{name}' not in scope")

    return ComputeResult(rd=rd, result=result & 0xFFFFFFFF, commit_stage="WB")


def compute_load(
    decoded: dict,
    proc: Processor,
    rs1_val: int | None = None,
) -> ComputeResult:
    """Describe a load whose memory read occurs at MEM and write at WB."""
    name = decoded["inst_name"]
    signed = name in ("lb", "lh")
    if rs1_val is None:
        rs1_val = proc.read_register(decoded["rs1"])
    imm = Memory.sign_extend(decoded["imm"], 12)
    addr = (rs1_val + imm) & 0xFFFFFFFF
    mem_op = {"kind": "load", "name": name, "addr": addr, "signed": signed}
    return ComputeResult(rd=decoded["rd"], mem_op=mem_op, commit_stage="WB")


def compute_store(
    decoded: dict,
    proc: Processor,
    rs1_val: int | None = None,
    rs2_val: int | None = None,
) -> ComputeResult:
    """Describe a store that commits at MEM."""
    name = decoded["inst_name"]
    if rs1_val is None:
        rs1_val = proc.read_register(decoded["rs1"])
    if rs2_val is None:
        rs2_val = proc.read_register(decoded["rs2"])
    imm = decoded["imm"]
    addr = (rs1_val + imm) & 0xFFFFFFFF
    mem_op = {"kind": "store", "name": name, "addr": addr, "val": rs2_val}
    return ComputeResult(mem_op=mem_op, commit_stage="MEM")


def compute_branch(
    decoded: dict,
    proc: Processor,
    pc: int,
    rs1_val: int | None = None,
    rs2_val: int | None = None,
) -> ComputeResult:
    """Resolve a branch for EX; ``next_pc`` is set only when taken."""
    name = decoded["inst_name"]
    if rs1_val is None:
        rs1_val = proc.read_register(decoded["rs1"])
    if rs2_val is None:
        rs2_val = proc.read_register(decoded["rs2"])

    if name == "beq":
        taken = rs1_val == rs2_val
    elif name == "bne":
        taken = rs1_val != rs2_val
    elif name == "blt":
        taken = Memory.sign_extend(rs1_val, 32) < Memory.sign_extend(rs2_val, 32)
    elif name == "bge":
        taken = Memory.sign_extend(rs1_val, 32) >= Memory.sign_extend(rs2_val, 32)
    elif name == "bltu":
        taken = rs1_val < rs2_val
    elif name == "bgeu":
        taken = rs1_val >= rs2_val
    else:
        raise NotImplementedError(f"compute_branch: '{name}' not in scope")

    next_pc = (pc + decoded["imm"]) & 0xFFFFFFFF if taken else None
    return ComputeResult(next_pc=next_pc, commit_stage="EX")


def compute_jal(decoded: dict, pc: int, inst_size: int) -> ComputeResult:
    """Compute JAL's target and link value."""
    link = (pc + inst_size) & 0xFFFFFFFF
    next_pc = (pc + decoded["imm"]) & 0xFFFFFFFF
    return ComputeResult(rd=decoded["rd"], result=link, next_pc=next_pc, commit_stage="WB")


def compute_jalr(
    decoded: dict,
    proc: Processor,
    pc: int,
    inst_size: int,
    rs1_val: int | None = None,
) -> ComputeResult:
    """Compute JALR's target and link value."""
    if rs1_val is None:
        rs1_val = proc.read_register(decoded["rs1"])
    imm = Memory.sign_extend(decoded["imm"], 12)
    link = (pc + inst_size) & 0xFFFFFFFF
    next_pc = (rs1_val + imm) & ~1 & 0xFFFFFFFF
    return ComputeResult(rd=decoded["rd"], result=link, next_pc=next_pc, commit_stage="WB")


def compute_utype(decoded: dict, proc: Processor, pc: int) -> ComputeResult:
    """U-Type (lui/auipc) — pure compute, commit at WB. Mirrors
    execute_instruction_utype."""
    name = decoded["inst_name"]
    imm = decoded["imm_31_12"] << 12
    if name == "lui":
        result = imm
    elif name == "auipc":
        result = pc + imm
    else:
        raise NotImplementedError(f"compute_utype: '{name}' not in scope")
    return ComputeResult(rd=decoded["rd"], result=result & 0xFFFFFFFF, commit_stage="WB")


def compute_csr(
    decoded: dict,
    proc: Processor,
    csr: CSRFile,
    rs1_val: int | None = None,
    instruction: int = 0,
    pc: int = 0,
) -> ComputeResult:
    """Compute a CSR read/modify result and optional WB write."""
    name = decoded["inst_name"]
    rd = decoded["rd"]
    rs1 = decoded["rs1"]
    csr_addr = decoded["csr_addr"]
    funct3 = decoded["funct3"]
    writes = (
        name in ("csrrw", "csrrwi")
        or (name in ("csrrs", "csrrc") and rs1 != 0)
        or (
            name in ("csrrsi", "csrrci")
            and decoded.get("uimm", 0) != 0
        )
    )
    if not csr.is_implemented(csr_addr) or (
        writes and not csr.is_writable(csr_addr)
    ):
        from .exceptions import illegal_instruction
        return ComputeResult(
            commit_stage="EX",
            trap=illegal_instruction(instruction, pc),
        )
    old_val = csr.read(csr_addr)
    if funct3 in (0b001, 0b010, 0b011):
        if rs1_val is None:
            src = proc.read_register(rs1)
        else:
            src = rs1_val
    else:
        src = decoded.get("uimm", rs1)

    new_val = None
    if name == "csrrw":
        new_val = src
    elif name == "csrrs":
        if rs1 != 0:
            new_val = old_val | src
    elif name == "csrrc":
        if rs1 != 0:
            new_val = old_val & ~src
    elif name == "csrrwi":
        new_val = decoded["uimm"]
    elif name == "csrrsi":
        if decoded["uimm"] != 0:
            new_val = old_val | decoded["uimm"]
    elif name == "csrrci":
        if decoded["uimm"] != 0:
            new_val = old_val & ~decoded["uimm"]
    else:
        raise NotImplementedError(f"compute_csr: '{name}' not in scope")

    res = ComputeResult(rd=rd, result=old_val, commit_stage="WB")
    if new_val is not None:
        res.csr_write = (csr_addr, new_val & 0xFFFFFFFF)
    return res


def compute_mret(decoded: dict, csr: CSRFile) -> ComputeResult:
    """Compute MRET's target and restored mstatus value."""
    mepc = csr.read(0x341)
    mstatus = csr.read(0x300)
    mpie = (mstatus >> 7) & 1
    if mpie:
        mstatus |= (1 << 3)
    else:
        mstatus &= ~(1 << 3)
    mstatus |= (1 << 7)
    mstatus &= ~(3 << 11)
    return ComputeResult(
        next_pc=mepc & 0xFFFFFFFF,
        commit_stage="WB",
        csr_write=(0x300, mstatus & 0xFFFFFFFF),
    )


def compute_ecall(decoded: dict) -> ComputeResult:
    """Request a machine-mode environment-call trap at EX."""
    from .exceptions import environment_call
    return ComputeResult(commit_stage="EX", trap=environment_call(mode=3))


def compute_ebreak(decoded: dict) -> ComputeResult:
    """EBREAK — request halt; commit at EX. step_clk performs proc.halt() at EX."""
    return ComputeResult(commit_stage="EX", halt=True)


def compute_fence(decoded: dict) -> ComputeResult:
    """Represent the core's decode-time FENCE/FENCE.I no-op."""
    return ComputeResult(commit_stage="ID")


def execute_instruction_mret(proc: Processor, csr: CSRFile):
    """Compute and commit MRET."""
    r = compute_mret({}, csr)
    if r.csr_write is not None:
        csr.write(r.csr_write[0], r.csr_write[1])
    proc.set_pc(r.next_pc)
    dbg(f"mret -> pc=0x{r.next_pc:08x}")
