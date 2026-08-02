"""Misaligned fetch, load, and store trap behavior."""

import pytest

from rv32i import Simulator
from rv32i.devices import register_default_devices
from rv32i.exceptions import (
    TrapException,
    load_address_misaligned,
    store_address_misaligned,
    instruction_address_misaligned,
)
from rv32i.memory import Memory
from rv32i.cache import Cache


# ---- hand-assembler helpers (no toolchain) -------------------------------
def encode_u(imm31_12, rd, opcode):
    return ((imm31_12 << 12) | (rd << 7) | opcode) & 0xFFFFFFFF


def encode_i(imm, rs1, funct3, rd, opcode=0b0010011):
    return (((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode) & 0xFFFFFFFF


def encode_load(imm, rs1, funct3, rd):
    return (((imm & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b0000011) & 0xFFFFFFFF


def encode_s(imm, rs2, rs1, funct3):
    return ((((imm >> 5) & 0x7F) << 25) | ((rs2 & 0x1F) << 20) | ((rs1 & 0x1F) << 15)
            | ((funct3 & 0x7) << 12) | ((imm & 0x1F) << 7) | 0b0100011) & 0xFFFFFFFF


EBREAK = 0x00100073


def make_simulator(prog):
    sim = Simulator(max_cycles=200)
    sim.mem.load_bytes(0, b"".join(w.to_bytes(4, "little") for w in prog))
    sim.timer = register_default_devices(sim.mem, sim.csr)
    sim.csr.write(0x305, 0)  # mtvec = 0 → a misaligned fault HALTs (no handler)
    sim.proc.reset(pc=0)
    return sim


# ---- exception factory unit tests ----------------------------------------
def test_load_misaligned_factory():
    e = load_address_misaligned(0x1001)
    assert e.mcause == 4
    assert e.mtval == 0x1001


def test_store_misaligned_factory():
    e = store_address_misaligned(0x1002)
    assert e.mcause == 6
    assert e.mtval == 0x1002


def test_instruction_misaligned_factory():
    e = instruction_address_misaligned(0x1003)
    assert e.mcause == 0
    assert e.mtval == 0x1003


# ---- low-level: Memory + Cache raise TrapException, not ValueError --------
def test_memory_read_word_misaligned_raises_trap():
    mem = Memory()
    with pytest.raises(TrapException) as ei:
        mem.read_word(0x1001)
    assert ei.value.mcause == 4 and ei.value.mtval == 0x1001


def test_memory_write_halfword_misaligned_raises_trap():
    mem = Memory()
    with pytest.raises(TrapException) as ei:
        mem.write_halfword(0x1001, 0xABCD)
    assert ei.value.mcause == 6 and ei.value.mtval == 0x1001


def test_cache_read_word_misaligned_raises_trap():
    c = Cache(Memory())
    with pytest.raises(TrapException) as ei:
        c.read_word(0x1003)
    assert ei.value.mcause == 4 and ei.value.mtval == 0x1003


def test_cache_write_word_misaligned_raises_trap():
    c = Cache(Memory())
    with pytest.raises(TrapException) as ei:
        c.write_word(0x1002, 0xDEADBEEF)
    assert ei.value.mcause == 6 and ei.value.mtval == 0x1002


# ---- byte accesses are NEVER misaligned (any address is byte-aligned) -----
@pytest.mark.parametrize("addr", [0x0, 0x1, 0x1001, 0x1003])
def test_byte_access_never_traps(addr):
    mem = Memory()
    mem.write_byte(addr, 0xAB)
    assert mem.read_byte(addr) == 0xAB  # no trap, no alignment requirement


# ---- end-to-end through both engines -------------------------------------
# lui x5,0x1 ; addi x5,x5,1  -> x5 = 0x1001 (word-misaligned)
_MISALIGNED_BASE = [encode_u(0x1, 5, 0b0110111), encode_i(1, 5, 0, 5)]


def run_step(sim):
    while not sim.proc.halted and sim.proc.cycles < sim.max_cycles:
        if sim.step() is None:
            break


def run_step_clk(sim):
    while not sim.proc.halted and sim.proc.cycles < sim.max_cycles:
        sim.step_clk()


@pytest.mark.parametrize("engine,runner", [("step", run_step), ("step_clk", run_step_clk)])
def test_misaligned_lw_traps(engine, runner):
    """LW from a word-misaligned address → mcause=4, mtval=faulting addr."""
    prog = _MISALIGNED_BASE + [encode_load(0, 5, 0b010, 1), EBREAK]
    sim = make_simulator(prog)
    runner(sim)
    assert sim.proc.halted, "machine should halt (mtvec=0 → no handler)"
    assert sim.csr.read(0x342) == 4, "mcause must be 4 (load address misaligned)"
    assert sim.csr.read(0x343) == 0x1001, "mtval must hold the faulting address"
    # mepc = PC of the faulting lw (0x08)
    assert sim.csr.read(0x341) == 0x08


@pytest.mark.parametrize("engine,runner", [("step", run_step), ("step_clk", run_step_clk)])
def test_misaligned_sw_traps(engine, runner):
    """SW to a word-misaligned address → mcause=6, mtval=faulting addr."""
    prog = _MISALIGNED_BASE + [encode_i(42, 0, 0, 6), encode_s(0, 6, 5, 0b010), EBREAK]
    sim = make_simulator(prog)
    runner(sim)
    assert sim.proc.halted
    assert sim.csr.read(0x342) == 6, "mcause must be 6 (store address misaligned)"
    assert sim.csr.read(0x343) == 0x1001
    assert sim.csr.read(0x341) == 0x0C  # PC of the faulting sw


@pytest.mark.parametrize("engine,runner", [("step", run_step), ("step_clk", run_step_clk)])
def test_misaligned_lh_traps(engine, runner):
    """LH from an odd address → mcause=4 (halfword misaligned)."""
    # x5 = 0x1001 (odd → not halfword-aligned)
    prog = _MISALIGNED_BASE + [encode_load(0, 5, 0b001, 1), EBREAK]
    sim = make_simulator(prog)
    runner(sim)
    assert sim.proc.halted
    assert sim.csr.read(0x342) == 4
    assert sim.csr.read(0x343) == 0x1001


def test_aligned_access_still_works():
    """Sanity: aligned accesses must NOT trap (regression guard)."""
    mem = Memory()
    mem.write_word(0x1000, 0xDEADBEEF)
    assert mem.read_word(0x1000) == 0xDEADBEEF
    mem.write_halfword(0x1000, 0x1234)
    assert mem.read_halfword(0x1000) == 0x1234


@pytest.mark.parametrize("engine", ["step", "step_clk", "step_pipe"])
def test_instruction_fetch_misalignment_traps_in_every_engine(engine):
    sim = Simulator(max_cycles=20)
    sim.proc.reset(pc=1)
    sim.csr.write(0x305, 0x100)

    for _ in range(4):
        getattr(sim, engine)()
        if sim.csr.read(0x342) == 0 and sim.csr.read(0x343) == 1:
            break

    assert sim.csr.read(0x341) == 1
    assert sim.csr.read(0x342) == 0
    assert sim.csr.read(0x343) == 1
    assert sim.proc.read_pc() == 0x100


@pytest.mark.parametrize("engine", ["step", "step_clk", "step_pipe"])
def test_reserved_compressed_encoding_takes_illegal_instruction_trap(engine):
    sim = Simulator(max_cycles=20)
    sim.mem.write_halfword(0, 0x0000)
    sim.proc.reset(pc=0)
    sim.csr.write(0x305, 0x100)

    for _ in range(5):
        getattr(sim, engine)()
        if sim.csr.read(0x342) == 2:
            break

    assert sim.csr.read(0x341) == 0
    assert sim.csr.read(0x342) == 2
    assert sim.csr.read(0x343) == 0
    assert sim.proc.read_pc() == 0x100


def test_single_cycle_trap_does_not_increment_minstret():
    sim = Simulator(max_cycles=10)
    sim.mem.write_word(0, 0x00000073)  # ECALL
    sim.proc.reset(pc=0)
    sim.csr.write(0x305, 0x100)

    sim.step()

    assert sim.csr.read(0x342) == 11
    assert sim.csr.read(0xB00) == 1
    assert sim.csr.read(0xB02) == 0
