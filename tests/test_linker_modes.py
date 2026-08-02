"""Build and execution tests for both linker modes."""
import os

import pytest

from rv32i.builder import (
    build,
    LINK_MODE_NO_LINKER,
    LINK_MODE_LINKER,
    DEFAULT_LINKER_SCRIPT,
)
from rv32i.elf_loader import load_elf
from rv32i.simulator import Simulator

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))


def toolchain_present() -> bool:
    from rv32i.builder import RISCV_GCC
    return os.path.isfile(RISCV_GCC)


pytestmark = pytest.mark.skipif(
    not toolchain_present(),
    reason="riscv64 toolchain not available (~/opt/riscv/bin/riscv64-unknown-elf-gcc)",
)


# A minimal program with an _start entry and a clearly-defined small global so
# the linker has .text + .data/.bss + __global_pointer$ to lay out.
_HELLO_C = """
volatile int g_counter = 7;

void _start(void) {
    g_counter += 1;
    asm volatile("wfi");
}
"""

_HELLO_S = """
.section .text
.globl _start

_start:
    addi x5, x0, 42
    ebreak
"""


@pytest.fixture
def hello_c(tmp_path):
    p = tmp_path / "hello.c"
    p.write_text(_HELLO_C)
    return str(p)


@pytest.fixture
def hello_s(tmp_path):
    p = tmp_path / "hello.s"
    p.write_text(_HELLO_S)
    return str(p)


class TestLinkModes:
    def test_no_linker_loads_at_default_text_base(self, hello_c):
        result = build(hello_c, link_mode=LINK_MODE_NO_LINKER)
        info = load_elf(result["elf_file"])
        # The simulator's conventional load base.
        assert info["text_addr"] == 0x00010000
        assert info["load_addr"] == 0x00010000
        assert info["entry_point"] == 0x00010000
        assert result["link_mode"] == LINK_MODE_NO_LINKER

    def test_linker_uses_default_script(self, hello_c):
        result = build(hello_c, link_mode=LINK_MODE_LINKER)
        info = load_elf(result["elf_file"])

        # default.ld pins .text at 0x00010000 and stack at 0x7FFFFFF0.
        assert info["text_addr"] == 0x00010000
        assert info["load_addr"] == 0x00010000
        assert info["entry_point"] == 0x00010000
        assert info["stack_top"] == 0x7FFFFFF0
        # The script defines __global_pointer$, which load_elf looks up.
        assert info["global_pointer"] is not None
        # gp must sit +0x800 past .data/.sdata, i.e. inside the load image region.
        assert 0x00010000 <= info["global_pointer"] < 0x7FFFFFF0
        assert result["link_mode"] == LINK_MODE_LINKER

    def test_linker_with_user_script_overrides_layout(self, hello_c, tmp_path):
        # Move .text to a non-default base via a user script to prove the
        # caller-provided script is actually honoured.
        user_ld = tmp_path / "user.ld"
        user_ld.write_text(
            'OUTPUT_ARCH("riscv")\n'
            "ENTRY(_start)\n"
            "SECTIONS\n"
            "{\n"
            "  .data 0x00018000 : { *(.data*) *(.sdata*) }\n"
            "  .text 0x00020000 : { *(.text*) }\n"
            "  .rodata : { *(.rodata*) }\n"
            "  .bss (NOLOAD) : { *(.bss*) *(COMMON) }\n"
            "  __stack_top = 0x70001230;\n"
            "}\n"
        )
        result = build(hello_c, link_mode=LINK_MODE_LINKER, linker_script=str(user_ld))
        info = load_elf(result["elf_file"])
        assert info["text_addr"] == 0x00020000
        assert info["entry_point"] == 0x00020000
        assert info["load_addr"] == 0x00018000
        assert info["stack_top"] == 0x70001230

    def test_default_linker_script_file_exists(self):
        assert os.path.isfile(DEFAULT_LINKER_SCRIPT)

    @pytest.mark.parametrize(
        "link_mode",
        [LINK_MODE_NO_LINKER, LINK_MODE_LINKER],
    )
    def test_raw_assembly_builds_in_both_link_modes(
        self,
        hello_s,
        link_mode,
    ):
        result = build(hello_s, link_mode=link_mode)
        info = load_elf(result["elf_file"])

        assert info["entry_point"] == 0x00010000
        assert info["load_addr"] == 0x00010000
        assert result["link_mode"] == link_mode

    def test_simulator_load_accepts_raw_assembly(self, hello_s):
        sim = Simulator(max_cycles=20)

        sim.load(hello_s)
        sim.run(delay=0)

        assert sim.proc.halted
        assert sim.proc.read_register(5) == 42
