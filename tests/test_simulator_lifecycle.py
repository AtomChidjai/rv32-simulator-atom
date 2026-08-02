"""Regression tests for simulator run/load/reset lifecycle boundaries."""

import pytest

from rv32i import Simulator
from rv32i.constants import MMIO_CONSOLE_OUT
from rv32i.devices import register_default_devices


def test_run_override_can_exceed_constructor_limit_without_hanging() -> None:
    sim = Simulator(max_cycles=2)
    sim.mem.load_bytes(0, b"\x01\x00" * 4)  # C.NOP stream

    sim.run(max_cycles=3, delay=0)

    assert sim.proc.cycles == 3
    assert sim.proc.read_pc() == 6
    assert sim.max_cycles == 2


def test_console_output_is_owned_by_the_frontend_callback(capsys) -> None:
    sim = Simulator()
    output: list[str] = []
    register_default_devices(sim.mem, sim.csr, on_console_write=output.append)

    sim.mem.write_byte(MMIO_CONSOLE_OUT, ord("X"))

    assert output == ["X"]
    assert capsys.readouterr().out == ""


def test_reset_clears_csr_trap_timer_and_input_state_but_keeps_program() -> None:
    sim = Simulator()
    sim.mem.write_word(0, 0x00100073)
    sim.timer = register_default_devices(sim.mem, sim.csr)
    sim.csr.write(0x340, 123)
    sim.csr.trap_log.append({"cause": 2})
    sim.timer.mtime = 99
    sim.timer.mtimecmp = 100
    sim._waiting_for_input = True
    sim.mem.wait_for_input()

    sim.reset(pc=0)

    assert sim.mem.read_word(0) == 0x00100073
    assert sim.csr.read(0x340) == 0
    assert sim.csr.trap_log == []
    assert sim.timer.mtime == 0
    assert sim.timer.mtimecmp == 0xFFFF
    assert not sim.waiting_for_input
    assert not sim.mem.waiting_for_input


def test_load_can_be_called_twice_without_duplicate_mmio(monkeypatch, tmp_path) -> None:
    binary = tmp_path / "program.bin"
    binary.write_bytes(b"\x01\x00")
    monkeypatch.setattr(
        "rv32i.simulator.build",
        lambda source: {"elf_file": "program.elf", "bin_file": str(binary)},
    )
    monkeypatch.setattr(
        "rv32i.simulator.load_elf",
        lambda path: {
            "entry_point": 0x200,
            "text_addr": 0x200,
            "load_addr": 0x180,
            "sections": [],
            "global_pointer": None,
            "stack_top": 0x70000000,
        },
    )

    sim = Simulator()
    sim.load("program.c")
    sim.load("program.c")

    assert sim.mem.read_halfword(0x180) == 0x0001
    assert sim.proc.read_pc() == 0x200


def test_public_observer_snapshots_are_detached() -> None:
    sim = Simulator()
    sim.mem.write_byte(0x100, 0x42)
    sim.csr.write(0x340, 0x1234)

    memory = sim.memory_snapshot()
    csrs = sim.csr_snapshot()
    changed_chunk = bytearray(memory[0])
    changed_chunk[0x100] = 0
    memory[0] = bytes(changed_chunk)
    csrs[0x340] = 0

    assert sim.mem.read_byte(0x100) == 0x42
    assert sim.csr.read(0x340) == 0x1234


def test_resume_input_clears_core_and_memory_wait_state() -> None:
    sim = Simulator()
    sim._waiting_for_input = True
    sim.mem.wait_for_input()

    assert sim.waiting_for_input
    sim.resume_input()
    assert not sim.waiting_for_input


@pytest.mark.parametrize("engine", ["step", "step_clk", "step_pipe"])
@pytest.mark.parametrize(
    ("instruction", "width"),
    [
        (0x0000006F, 4),  # jal x0, 0
        (0x00000063, 4),  # beq x0, x0, 0
        (0x00000067, 4),  # jalr x0, 0(x0)
        (0x0000A001, 2),  # c.j 0
        (0x30200073, 4),  # mret with mepc=0
    ],
)
def test_explicit_self_target_preserves_pc(
    engine: str,
    instruction: int,
    width: int,
) -> None:
    sim = Simulator(max_cycles=100)
    sim.mem.load_bytes(0, instruction.to_bytes(width, "little") + bytes(32))
    sim.proc.reset(pc=0)

    snapshots = []
    for _ in range(64):
        snapshot = getattr(sim, engine)()
        if snapshot is not None:
            snapshots.append(snapshot)
        if len(snapshots) == 2:
            break

    assert [snapshot["pc"] for snapshot in snapshots] == [0, 0]
