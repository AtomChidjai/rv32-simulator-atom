"""CSR writes may target only the simulator's implemented CSR set."""

import pytest

from rv32i.simulator import Simulator


EBREAK = 0x00100073
UNKNOWN_CSR = 0x7C0
MISA = 0x301


def encode_csr(csr_addr: int, source: int, funct3: int, rd: int = 5) -> int:
    return (
        (csr_addr << 20)
        | (source << 15)
        | (funct3 << 12)
        | (rd << 7)
        | 0b1110011
    ) & 0xFFFFFFFF


def make_simulator(instruction: int) -> Simulator:
    sim = Simulator(max_cycles=100)
    sim.mem.load_bytes(
        0,
        instruction.to_bytes(4, "little") + EBREAK.to_bytes(4, "little"),
    )
    sim.proc.reset(pc=0)
    sim.proc.write_register(1, 1)
    return sim


def run(sim: Simulator, engine: str) -> None:
    for _ in range(100):
        if sim.proc.halted:
            break
        getattr(sim, engine)()
    assert sim.proc.halted


@pytest.mark.parametrize("engine", ["step", "step_clk", "step_pipe"])
@pytest.mark.parametrize("funct3", [0b001, 0b010, 0b011])
def test_unknown_register_csr_writes_trap(engine: str, funct3: int) -> None:
    sim = make_simulator(encode_csr(UNKNOWN_CSR, 1, funct3))

    run(sim, engine)

    assert not sim.csr.is_implemented(UNKNOWN_CSR)
    assert sim.csr.trap_log[0]["cause"] == 2
    assert sim.csr.trap_log[0]["mtval"] == encode_csr(UNKNOWN_CSR, 1, funct3)
    assert sim.proc.read_register(5) == 0


@pytest.mark.parametrize("engine", ["step", "step_clk", "step_pipe"])
@pytest.mark.parametrize("funct3", [0b101, 0b110, 0b111])
def test_unknown_immediate_csr_writes_trap(engine: str, funct3: int) -> None:
    sim = make_simulator(encode_csr(UNKNOWN_CSR, 1, funct3))

    run(sim, engine)

    assert not sim.csr.is_implemented(UNKNOWN_CSR)
    assert sim.csr.trap_log[0]["cause"] == 2
    assert sim.csr.trap_log[0]["mtval"] == encode_csr(UNKNOWN_CSR, 1, funct3)
    assert sim.proc.read_register(5) == 0


@pytest.mark.parametrize("engine", ["step", "step_clk", "step_pipe"])
@pytest.mark.parametrize("funct3", [0b010, 0b011, 0b110, 0b111])
def test_unknown_zero_source_csr_access_traps(
    engine: str,
    funct3: int,
) -> None:
    instruction = encode_csr(UNKNOWN_CSR, 0, funct3)
    sim = make_simulator(instruction)

    run(sim, engine)

    assert not sim.csr.is_implemented(UNKNOWN_CSR)
    assert sim.csr.trap_log[0]["cause"] == 2
    assert sim.csr.trap_log[0]["mtval"] == instruction
    assert sim.proc.read_register(5) == 0
    assert sim.csr.read(0xB02) == 0


@pytest.mark.parametrize("engine", ["step", "step_clk", "step_pipe"])
@pytest.mark.parametrize(
    "funct3",
    [0b001, 0b010, 0b011, 0b101, 0b110, 0b111],
)
def test_read_only_csr_writes_trap(engine: str, funct3: int) -> None:
    instruction = encode_csr(MISA, 1, funct3)
    sim = make_simulator(instruction)

    run(sim, engine)

    assert sim.csr.trap_log[0]["cause"] == 2
    assert sim.csr.trap_log[0]["mtval"] == instruction
    assert sim.proc.read_register(5) == 0
    assert sim.csr.read(MISA) == 0x40001104
    assert sim.csr.read(0xB02) == 0


@pytest.mark.parametrize("engine", ["step", "step_clk", "step_pipe"])
@pytest.mark.parametrize("funct3", [0b010, 0b011, 0b110, 0b111])
def test_read_only_csr_zero_source_access_reads_without_writing(
    engine: str,
    funct3: int,
) -> None:
    sim = make_simulator(encode_csr(MISA, 0, funct3))

    run(sim, engine)

    assert sim.csr.trap_log == []
    assert sim.proc.read_register(5) == 0x40001104
    assert sim.csr.read(MISA) == 0x40001104
    assert sim.csr.read(0xB02) == 1


def test_direct_unknown_csr_write_does_not_create_register() -> None:
    sim = Simulator()

    sim.csr.write(UNKNOWN_CSR, 0x12345678)

    assert not sim.csr.is_implemented(UNKNOWN_CSR)
    assert not sim.csr.is_writable(UNKNOWN_CSR)
    assert not sim.csr.is_writable(MISA)
    assert sim.csr.is_writable(0x300)
    assert sim.csr.read(UNKNOWN_CSR) == 0
