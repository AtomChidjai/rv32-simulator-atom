import os

import pytest

from .test_golden_trace_utils import (
    ABI_NAMES,
    RISCV_GCC,
    SPIKE,
    SpikeRunner,
    executable_available,
)
from .conftest import run_simulator_to_halt

PROGRAMS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "programs", "isa")

pytestmark = pytest.mark.skipif(
    not (executable_available(RISCV_GCC) and executable_available(SPIKE)),
    reason="Spike golden-trace toolchain is not available",
)

# Core ISA coverage — one program per instruction format / extension:
PROGRAMS = [
    "test_rtype.c",        # R-type ALU (add/sub/xor/or/and/sll/srl/sra/slt/sltu)
    "test_itype.c",        # I-type immediate ALU (addi/xori/.../sltiu/slli/srli/srai)
    "test_load_store.c",   # lw/lh/lb/lbu/lhu + sw/sh/sb
    "test_branch.c",       # beq/bne/blt/bge/bltu/bgeu
    "test_utype.c",        # lui/auipc
    "test_m_ext.c",        # M-extension (mul/mulh/div/rem/...)
]

# Edge-case coverage — architectural corner cases that are easy to get wrong
# and that the core programs above only touch lightly:
EDGE_PROGRAMS = [
    "test_jal.c",          # JAL/JALR control flow (forward jump + call/return)
    "test_m_edge.c",       # mul overflow, div/rem by zero, INT_MIN/-1 overflow
    "test_ls_edge.c",      # sign vs. zero extension, sub-word store overlap
]


@pytest.fixture
def spike():
    return SpikeRunner()


def assert_registers_match(program, spike_regs, sim):
    """Compare all 32 registers between Spike's golden state and our simulator."""
    for reg_name in ABI_NAMES:
        if reg_name == "zero":
            continue
        spike_val = spike_regs.get(reg_name, 0)
        sim_val = sim.proc.read_register(ABI_NAMES.index(reg_name))
        assert sim_val == spike_val, (
            f"{program}: register {reg_name} mismatch: "
            f"sim=0x{sim_val:08x} spike=0x{spike_val:08x}"
        )


@pytest.mark.parametrize("program", PROGRAMS)
def test_golden_trace(spike, program):
    """Core ISA: every register in our sim must match Spike after running the
    same C program to ebreak. Catches end-to-end pipeline bugs."""
    c_file = os.path.join(PROGRAMS_DIR, program)
    spike_regs = spike.get_golden_state(c_file)
    sim = run_simulator_to_halt(c_file)
    assert_registers_match(program, spike_regs, sim)


@pytest.mark.parametrize("program", EDGE_PROGRAMS)
def test_golden_trace_edge(spike, program):
    """Architectural edge cases (jumps, M-ext overflow/div-by-zero, sign
    extension) compared against Spike — same mechanism as the core suite."""
    c_file = os.path.join(PROGRAMS_DIR, program)
    spike_regs = spike.get_golden_state(c_file)
    sim = run_simulator_to_halt(c_file)
    assert_registers_match(program, spike_regs, sim)
