"""Headless execution-state predicates shared by the GUI and its tests."""

from collections.abc import Collection
from dataclasses import dataclass

from rv32i.simulator import Simulator


@dataclass(frozen=True)
class _ModeUIState:
    """Visibility of controls and panels whose meaning is mode-specific."""

    cache_stalls: bool
    pipeline_config: bool
    pipeline_panel: bool
    multicycle_panel: bool


_MODE_UI = {
    "single": _ModeUIState(False, False, False, False),
    "multi": _ModeUIState(True, False, False, True),
    "pipe": _ModeUIState(True, True, True, False),
}
_MODE_CYCLE_SCALE = {"single": 1, "multi": 5, "pipe": 5}


def mode_ui_state(mode: str) -> _ModeUIState:
    """Return the mode-specific visibility contract."""

    try:
        return _MODE_UI[mode]
    except KeyError as exc:
        raise ValueError(f"unknown execution mode: {mode!r}") from exc


def pipeline_drained(sim: Simulator) -> bool:
    """Return whether every real pipeline latch is a bubble."""

    return sim.pipeline_state().drained


def pipeline_fetch_pc(sim: Simulator) -> int | None:
    """Return the instruction currently fetched at the pipeline front."""

    return sim.pipeline_state().fetch_pc


def current_breakpoint_pc(sim: Simulator, mode: str) -> int | None:
    """Return the address eligible to hit a GUI breakpoint."""

    if mode == "pipe":
        return pipeline_fetch_pc(sim)
    return sim.proc.read_pc()


def assembly_highlight_pc(
    sim: Simulator,
    mode: str,
    known_pcs: Collection[int] | None = None,
) -> int:
    """Return the real instruction address to highlight for the active mode."""

    if mode != "pipe":
        return sim.proc.read_pc()
    pipeline = sim.pipeline_state()
    candidates: list[int] = []
    fetch_pc = pipeline.fetch_pc
    if fetch_pc is not None:
        candidates.append(fetch_pc)
    for latch in (pipeline.id_ex, pipeline.ex_mem, pipeline.mem_wb):
        if not latch.bubble:
            candidates.append(latch.pc)
    candidates.append(sim.proc.read_pc())
    if known_pcs is not None:
        for pc in candidates:
            if pc in known_pcs:
                return pc
    return candidates[0]


def can_advance(sim: Simulator, mode: str) -> bool:
    """Allow a halted pipeline to advance only while it still must drain."""

    if cycle_limit_reached(sim, mode):
        return False
    return not sim.proc.halted or (mode == "pipe" and not pipeline_drained(sim))


def cycle_limit_reached(sim: Simulator, mode: str) -> bool:
    """Return whether the active engine must stop at its execution budget."""

    draining = mode == "pipe" and sim.pipeline_state().draining
    return sim.csr.read(0xB00) >= sim.max_cycles and not draining


def execution_in_flight(sim: Simulator) -> bool:
    """Return whether changing engines would abandon microarchitectural work."""

    return sim.has_in_flight_work()


def mode_cycle_limit(
    base_instructions: int,
    *,
    current_cycles: int,
    retired: int,
    mode: str,
) -> int:
    """Translate the remaining instruction budget into the mode's clocks."""

    try:
        scale = _MODE_CYCLE_SCALE[mode]
    except KeyError as exc:
        raise ValueError(f"unknown execution mode: {mode!r}") from exc
    remaining = max(0, base_instructions - retired)
    return current_cycles + remaining * scale
