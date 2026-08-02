"""Latch and observer definitions for the cycle-accurate pipeline engine."""

from dataclasses import dataclass

S_IF, S_ID, S_EX, S_MEM, S_WB = 0, 1, 2, 3, 4

@dataclass
class Latch:
    """One inter-stage payload; ``bubble`` means there is nothing to commit."""

    bubble: bool = True
    fetch_id: int | None = None
    pc: int = 0
    instruction: int = 0
    inst_size: int = 4
    decoded: dict | None = None
    rd: int | None = None
    result: int | None = None
    mem_op: dict | None = None
    next_pc: int | None = None
    commit_stage: str | None = None
    csr_write: tuple[int, int] | None = None
    halt: bool = False
    trap: object | None = None
    predicted_next_pc: int | None = None

    @classmethod
    def bubble_slot(cls) -> "Latch":
        """A fresh bubble (NOP) latch — nothing to commit, no in-flight data."""
        return cls()

    @classmethod
    def fetched(cls, pc: int, instruction: int, inst_size: int) -> "Latch":
        """A freshly-fetched instruction entering IF/ID."""
        return cls(bubble=False, pc=pc, instruction=instruction, inst_size=inst_size)


@dataclass(frozen=True)
class PipelineLatchSnapshot:
    """Read-only GUI view of one inter-stage latch."""

    bubble: bool
    fetch_id: int | None
    pc: int
    mnemonic: str | None


@dataclass(frozen=True)
class BranchPredictionSnapshot:
    """Detached conditional-branch prediction counters."""

    total: int
    predicted_taken: int
    predicted_not_taken: int
    correct: int
    incorrect: int

    @property
    def accuracy(self) -> float:
        return (self.correct / self.total) if self.total else 0.0


@dataclass(frozen=True)
class PipelineSnapshot:
    """Read-only copy of the pipeline state exposed by ``Simulator``."""

    fetch_pc: int | None
    if_id: PipelineLatchSnapshot
    id_ex: PipelineLatchSnapshot
    ex_mem: PipelineLatchSnapshot
    mem_wb: PipelineLatchSnapshot
    drained: bool
    draining: bool
    mcycle: int
    minstret: int
    stalls: int
    flushes: int
    branch_prediction: BranchPredictionSnapshot
    trace: tuple[dict, ...]
