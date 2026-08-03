"""Curated source programs exposed by the GUI example selector."""

from dataclasses import dataclass
from pathlib import Path

from rv32i.builder import DEFAULT_ARCH, DEFAULT_LINK_MODE

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_LANGUAGES = ("c", "assembly")


@dataclass(frozen=True)
class ExampleProgram:
    """C and assembly variants with the build settings needed to run them."""

    id: str
    label: str
    c_relative_path: str
    assembly_relative_path: str
    arch: str = DEFAULT_ARCH
    link_mode: str = DEFAULT_LINK_MODE

    def path_for(self, language: str) -> Path:
        if language == "c":
            return _PROJECT_ROOT / self.c_relative_path
        if language == "assembly":
            return _PROJECT_ROOT / self.assembly_relative_path
        raise ValueError(f"unsupported source language: {language!r}")


DEFAULT_EXAMPLE_ID = "instruction-tour"

EXAMPLE_PROGRAMS = (
    ExampleProgram(
        DEFAULT_EXAMPLE_ID,
        "Basics / Instruction tour",
        "programs/isa/demo_all_types.c",
        "programs/isa/demo_all_types.s",
    ),
    ExampleProgram(
        "hello-terminal",
        "I/O / Hello terminal",
        "programs/examples/hello_terminal.c",
        "programs/examples/hello_terminal.s",
    ),
    ExampleProgram(
        "echo-terminal",
        "I/O / Echo terminal input",
        "programs/io/io_input_test.c",
        "programs/io/io_input_test.s",
    ),
    ExampleProgram(
        "bubble-sort",
        "Algorithms / Bubble sort",
        "programs/examples/bubble_sort.c",
        "programs/examples/bubble_sort.s",
    ),
    ExampleProgram(
        "pipeline-data-hazard",
        "Pipeline / Data forwarding",
        "programs/pipeline_data_hazard.c",
        "programs/pipeline_data_hazard.s",
    ),
    ExampleProgram(
        "pipeline-control-hazard",
        "Pipeline / Control hazard",
        "programs/pipeline_control_hazard.c",
        "programs/pipeline_control_hazard.s",
    ),
    ExampleProgram(
        "cache-spatial-locality",
        "Cache / Spatial locality",
        "programs/io/spatial_locality.c",
        "programs/io/spatial_locality.s",
    ),
    ExampleProgram(
        "compressed-instructions",
        "ISA / Compressed instructions",
        "programs/io/test_compressed.c",
        "programs/io/test_compressed.s",
        arch="rv32ic_zicsr",
    ),
    ExampleProgram(
        "timer-interrupt",
        "Interrupts / Timer",
        "programs/io/simple_timer_interrupt.c",
        "programs/io/simple_timer_interrupt.s",
    ),
)

EXAMPLE_PROGRAMS_BY_ID = {example.id: example for example in EXAMPLE_PROGRAMS}
