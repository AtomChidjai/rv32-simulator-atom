"""Headless regression tests for the GUI/pipeline execution-state seam."""

import asyncio

from gui.app import SimulatorUI
from gui.pipeline_control import (
    assembly_highlight_pc,
    current_breakpoint_pc,
    can_advance,
    cycle_limit_reached,
    execution_in_flight,
    mode_cycle_limit,
    mode_ui_state,
    pipeline_drained,
)
from rv32i.devices import register_default_devices
from rv32i.simulator import Simulator
from tests.test_pipeline import EBREAK, encode_i, encode_words


class _TimerStub:
    def __init__(self) -> None:
        self.deactivated = False

    def deactivate(self) -> None:
        self.deactivated = True


class _TerminalStub:
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, text: str) -> None:
        self.writes.append(text)


def make_simulator(words: list[int]) -> Simulator:
    sim = Simulator(max_cycles=100)
    sim.mem.load_bytes(0, encode_words(words))
    sim.timer = register_default_devices(sim.mem, sim.csr)
    sim.proc.reset(pc=0)
    return sim


def headless_ui(sim: Simulator) -> SimulatorUI:
    ui = SimulatorUI.__new__(SimulatorUI)
    ui.sim = sim
    ui.run_timer = _TimerStub()
    ui._init_sp = 0x7FFFFFF0
    ui._init_gp = None
    ui._input_buffer = []
    ui._term_lines = []
    ui._mem_snapshot = {
        idx: bytearray(chunk) for idx, chunk in sim.mem.chunks.items()
    }
    ui._max_cycles_base = sim.max_cycles
    ui._mode = "pipe"
    ui._breakpoints = set()
    return ui


def test_breakpoint_poll_ignores_disconnected_client_timeout(monkeypatch) -> None:
    async def disconnected_client(script: str) -> None:
        raise TimeoutError

    monkeypatch.setattr("gui.app.ui.run_javascript", disconnected_client)
    asyncio.run(SimulatorUI.__new__(SimulatorUI).check_breakpoint_click())


def test_pipeline_highlight_and_breakpoint_follow_fetched_instruction() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK])

    assert current_breakpoint_pc(sim, "pipe") is None
    sim.step_pipe()

    assert sim.proc.read_pc() == 4
    assert assembly_highlight_pc(sim, "pipe", {0, 4}) == 0
    assert current_breakpoint_pc(sim, "pipe") == 0


def test_pipeline_highlight_keeps_final_listed_instruction_while_it_is_live() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), 0x00000013])  # final nop
    for _ in range(3):
        sim.step_pipe()

    assert sim.if_id.pc == 8
    assert sim.id_ex.pc == 4
    assert assembly_highlight_pc(sim, "pipe", {0, 4}) == 4


def test_pipeline_breakpoint_stops_last_instruction_before_id() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), 0x00000013])  # final nop
    sim.step_pipe()
    sim.step_pipe()
    ui = headless_ui(sim)
    ui._breakpoints.add(4)
    statuses: list[str] = []
    ui.apply_status = lambda message, color: statuses.append(message)
    cycle = sim.csr.read(0xB00)

    ui.auto_tick()

    assert ui.run_timer.deactivated
    assert sim.csr.read(0xB00) == cycle
    assert sim.if_id.pc == 4
    assert not sim.proc.halted
    assert statuses == ["Breakpoint hit @ 0x00000004"]


def test_pipeline_run_route_drains_after_ebreak() -> None:
    """The GUI run predicate keeps clocking until EBREAK acts at WB."""
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK])
    saw_draining = False

    while can_advance(sim, "pipe"):
        sim.step_pipe()
        saw_draining |= sim.pipeline_state().draining

    assert saw_draining
    assert sim.proc.read_register(1) == 1
    assert pipeline_drained(sim)


def test_compile_boundary_drops_old_pipeline_work() -> None:
    """Reloading through the shared reset boundary cannot retire old latches."""
    sim = make_simulator([encode_i(99, 0, 0, 5), EBREAK])
    ui = headless_ui(sim)
    for _ in range(3):
        sim.step_pipe()
    assert execution_in_flight(sim)

    sim.mem.reset()
    sim.mem.load_bytes(0, encode_words([encode_i(7, 0, 0, 2), EBREAK]))
    sim.timer = register_default_devices(sim.mem, sim.csr)
    ui._mem_snapshot = {
        idx: bytearray(chunk) for idx, chunk in sim.mem.chunks.items()
    }
    ui.reset_loaded_state(restore_memory=False)

    while can_advance(sim, "pipe"):
        sim.step_pipe()

    assert sim.proc.read_register(2) == 7
    assert sim.proc.read_register(5) == 0
    assert pipeline_drained(sim)


def test_mode_switch_with_live_pipeline_resets_loaded_state() -> None:
    """Changing engines mid-flight restores boot PC/registers and empty latches."""
    sim = make_simulator([encode_i(3, 0, 0, 1), EBREAK])
    ui = headless_ui(sim)
    sim._entry_point = 0
    sim.step_pipe()
    assert execution_in_flight(sim)
    assert sim.proc.read_pc() != 0

    statuses: list[str] = []
    ui.refresh = lambda: None
    ui.update_mc_panel = lambda: None
    ui.apply_status = lambda message, color: statuses.append(message)
    ui.on_mode_change("single")

    assert ui._mode == "single"
    assert ui.run_timer.deactivated
    assert sim.proc.read_pc() == 0
    assert sim.proc.read_register(2) == ui._init_sp
    assert pipeline_drained(sim)
    assert any(message.startswith("Execution reset;") for message in statuses)


def test_mode_switch_without_live_work_stops_run_and_preserves_state() -> None:
    sim = make_simulator([encode_i(3, 0, 0, 1), EBREAK])
    ui = headless_ui(sim)
    sim.proc.set_pc(4)
    sim.proc.cycles = 20
    sim.csr._csr[0xB00] = 20
    sim.csr._csr[0xB02] = 10

    ui.refresh = lambda: None
    ui.update_mc_panel = lambda: None
    ui.apply_status = lambda message, color: None
    ui.on_mode_change("single")

    assert ui.run_timer.deactivated
    assert sim.proc.read_pc() == 4
    assert sim.proc.cycles == 20
    assert sim.max_cycles == 110


def test_multicycle_uses_main_step_for_one_clock() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK])
    ui = headless_ui(sim)
    ui._mode = "multi"
    ui.refresh = lambda: None
    ui.update_mc_panel = lambda **kwargs: None
    statuses: list[str] = []
    ui.apply_status = lambda message, color: statuses.append(message)

    ui.step()

    assert sim.csr.read(0xB00) == 1
    assert sim.multicycle_state() is not None
    assert statuses == ["Multi-cycle: one clock advanced"]


def test_mode_ui_state_exposes_only_relevant_controls_and_panels() -> None:
    single = mode_ui_state("single")
    assert not single.cache_stalls
    assert not single.pipeline_config
    assert not single.pipeline_panel
    assert not single.multicycle_panel

    multi = mode_ui_state("multi")
    assert multi.cache_stalls
    assert not multi.pipeline_config
    assert not multi.pipeline_panel
    assert multi.multicycle_panel

    pipe = mode_ui_state("pipe")
    assert pipe.cache_stalls
    assert pipe.pipeline_config
    assert pipe.pipeline_panel
    assert not pipe.multicycle_panel


def test_mode_cycle_limit_preserves_remaining_instruction_budget() -> None:
    assert mode_cycle_limit(500, current_cycles=20, retired=10, mode="single") == 510
    assert mode_cycle_limit(500, current_cycles=20, retired=10, mode="multi") == 2470
    assert mode_cycle_limit(500, current_cycles=20, retired=10, mode="pipe") == 2470


def test_pipeline_can_drain_after_reaching_cycle_limit() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK])
    sim.max_cycles = 4
    for _ in range(4):
        sim.step_pipe()

    assert sim.pipeline_state().draining
    assert not cycle_limit_reached(sim, "pipe")
    assert can_advance(sim, "pipe")

    while not sim.pipeline_state().drained:
        sim.step_pipe()

    assert sim.proc.read_register(1) == 1


def test_gui_cycle_limit_uses_mcycle_not_processor_counter() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK])
    sim.max_cycles = 5
    sim.proc.cycles = 99
    sim.csr._csr[0xB00] = 4
    assert not cycle_limit_reached(sim, "single")

    sim.csr._csr[0xB00] = 5
    assert cycle_limit_reached(sim, "single")


def test_gui_reset_restores_cycle_budget_and_clears_visible_terminal() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK])
    ui = headless_ui(sim)
    ui._max_cycles_base = 100
    sim.max_cycles = 7
    ui.terminal = _TerminalStub()
    ui._term_lines.extend(["old output"])

    ui.reset_loaded_state()

    assert sim.max_cycles == 500
    assert ui._term_lines == []
    assert ui.terminal.writes == ["\x1bc"]


def test_waiting_for_input_counts_as_in_flight_execution() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK])
    sim._waiting_for_input = True
    sim.mem._waiting_for_input = True
    assert execution_in_flight(sim)


def test_fresh_simulator_has_no_in_flight_execution() -> None:
    sim = Simulator()
    assert not sim.mem._waiting_for_input
    assert not execution_in_flight(sim)

    sim.mem._waiting_for_input = True
    sim.mem.reset()
    assert not sim.mem._waiting_for_input


def test_pipeline_snapshot_is_detached_and_fetch_ids_reset() -> None:
    sim = make_simulator([encode_i(1, 0, 0, 1), EBREAK])
    for _ in range(5):
        sim.step_pipe()

    snapshot = sim.pipeline_state()
    ids_by_pc: dict[int, set[int]] = {}
    for entry in snapshot.trace:
        for slot in entry["slots"].values():
            if slot is not None:
                ids_by_pc.setdefault(slot["pc"], set()).add(slot["fetch_id"])
    assert ids_by_pc[0] == {0}
    assert ids_by_pc[4] == {1}
    assert any(entry["retired"] == 0 for entry in snapshot.trace)

    snapshot.trace[0]["cycle"] = -1
    assert sim.pipe_trace[0]["cycle"] != -1

    sim.reset(pc=0)
    sim.step_pipe()
    assert sim.if_id.fetch_id == 0
