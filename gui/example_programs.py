"""Curated source programs exposed by the GUI example selector."""

from dataclasses import dataclass
from pathlib import Path

from rv32i.builder import DEFAULT_ARCH, DEFAULT_LINK_MODE

_PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ExampleProgram:
    """One source file and the build settings needed to run it."""

    id: str
    label: str
    relative_path: str
    arch: str = DEFAULT_ARCH
    link_mode: str = DEFAULT_LINK_MODE

    @property
    def path(self) -> Path:
        return _PROJECT_ROOT / self.relative_path

    @property
    def language(self) -> str:
        return "assembly" if self.path.suffix.lower() == ".s" else "c"


DEFAULT_EXAMPLE_ID = "instruction-tour"

EXAMPLE_PROGRAMS = (
    ExampleProgram(
        DEFAULT_EXAMPLE_ID,
        "Basics / Instruction tour",
        "programs/isa/demo_all_types.c",
    ),
    ExampleProgram(
        "hello-terminal",
        "I/O / Hello terminal",
        "programs/examples/hello_terminal.c",
    ),
    ExampleProgram(
        "echo-terminal",
        "I/O / Echo terminal input",
        "programs/io/io_input_test.c",
    ),
    ExampleProgram(
        "bubble-sort",
        "Algorithms / Bubble sort",
        "programs/examples/bubble_sort.c",
    ),
    ExampleProgram(
        "pipeline-data-hazard",
        "Pipeline / Data forwarding",
        "programs/pipeline_data_hazard.c",
    ),
    ExampleProgram(
        "pipeline-control-hazard",
        "Pipeline / Control hazard",
        "programs/pipeline_control_hazard.c",
    ),
    ExampleProgram(
        "cache-spatial-locality",
        "Cache / Spatial locality",
        "programs/io/spatial_locality.c",
    ),
    ExampleProgram(
        "compressed-instructions",
        "ISA / Compressed instructions",
        "programs/io/test_compressed.c",
        arch="rv32ic_zicsr",
    ),
    ExampleProgram(
        "timer-interrupt",
        "Interrupts / Timer",
        "programs/io/simple_timer_interrupt.c",
    ),
)

EXAMPLE_PROGRAMS_BY_ID = {example.id: example for example in EXAMPLE_PROGRAMS}
