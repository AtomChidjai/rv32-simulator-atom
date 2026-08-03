"""Catalog and end-to-end checks for GUI example programs."""

import shutil
from pathlib import Path

import pytest

from gui.example_programs import (
    DEFAULT_EXAMPLE_ID,
    EXAMPLE_PROGRAMS,
    EXAMPLE_PROGRAMS_BY_ID,
    SOURCE_LANGUAGES,
)
from rv32i.builder import RISCV_GCC, build
from rv32i.elf_loader import load_elf
from rv32i.simulator import Simulator


TOOLCHAIN_PRESENT = (
    Path(RISCV_GCC).is_file() or shutil.which(RISCV_GCC) is not None
)
needs_toolchain = pytest.mark.skipif(
    not TOOLCHAIN_PRESENT,
    reason="riscv64 toolchain is not available",
)


def test_example_catalog_has_unique_ids_labels_and_existing_sources() -> None:
    assert DEFAULT_EXAMPLE_ID in EXAMPLE_PROGRAMS_BY_ID
    assert len(EXAMPLE_PROGRAMS_BY_ID) == len(EXAMPLE_PROGRAMS)
    assert len({example.label for example in EXAMPLE_PROGRAMS}) == len(
        EXAMPLE_PROGRAMS
    )

    for example in EXAMPLE_PROGRAMS:
        for language in SOURCE_LANGUAGES:
            path = example.path_for(language)
            assert path.is_file(), path
            assert path.read_text(encoding="utf-8").strip()
            assert path.suffix == (".c" if language == "c" else ".s")


@needs_toolchain
@pytest.mark.parametrize(
    ("example", "language"),
    [
        (example, language)
        for example in EXAMPLE_PROGRAMS
        for language in SOURCE_LANGUAGES
    ],
    ids=lambda value: value.id if hasattr(value, "id") else value,
)
def test_every_example_compiles_with_its_catalog_settings(example, language) -> None:
    result = build(
        str(example.path_for(language)),
        march=example.arch,
        link_mode=example.link_mode,
    )

    info = load_elf(result["elf_file"])

    assert Path(result["bin_file"]).stat().st_size > 0
    assert info["entry_point"] >= 0x10000


@needs_toolchain
@pytest.mark.parametrize("language", SOURCE_LANGUAGES)
@pytest.mark.parametrize(
    ("example_id", "expected_output", "cycle_ceiling"),
    [
        ("hello-terminal", "Hello from RISC-V!\n", 250),
        ("bubble-sort", "1 2 3 4\n", 200),
    ],
)
def test_functional_examples_run_to_halt_and_print(
    example_id: str, expected_output: str, cycle_ceiling: int, language: str
) -> None:
    example = EXAMPLE_PROGRAMS_BY_ID[example_id]
    simulator = Simulator(trace=False, max_cycles=500)

    simulator.load(str(example.path_for(language)))
    simulator.run(max_cycles=500, delay=0)

    assert simulator.proc.halted
    assert simulator.proc.cycles <= cycle_ceiling
    assert "".join(simulator.console_buffer) == expected_output
