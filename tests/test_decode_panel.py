"""Structured Decode-panel models and native encoding layouts."""

import pytest

from gui.decode_panel import build_decode_panel
from rv32i.decoder import Decoder


def decode_view(instruction: int, *, pc: int = 0x1000, width: int = 4):
    decoder = Decoder()
    decoded = (
        decoder.decode_compressed(instruction)
        if width == 2
        else decoder.decoding(instruction)
    )
    decoded["_inst_size"] = width
    html, source = build_decode_panel(instruction, decoded, pc)
    assert source is not None
    assert sum(field["bits"] for field in source["reg"]) == width * 8
    return html, source


def s_type(imm: int, rs2: int, rs1: int, funct3: int) -> int:
    raw = imm & 0xFFF
    return (
        ((raw >> 5) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | ((raw & 0x1F) << 7)
        | 0b0100011
    )


def b_type(imm: int, rs2: int, rs1: int, funct3: int) -> int:
    raw = imm & 0x1FFF
    return (
        (((raw >> 12) & 1) << 31)
        | (((raw >> 5) & 0x3F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (funct3 << 12)
        | (((raw >> 1) & 0xF) << 8)
        | (((raw >> 11) & 1) << 7)
        | 0b1100011
    )


def j_type(imm: int, rd: int) -> int:
    raw = imm & 0x1FFFFF
    return (
        (((raw >> 20) & 1) << 31)
        | (((raw >> 1) & 0x3FF) << 21)
        | (((raw >> 11) & 1) << 20)
        | (((raw >> 12) & 0xFF) << 12)
        | (rd << 7)
        | 0b1101111
    )


def test_empty_and_trap_states_do_not_create_bitfields() -> None:
    html, source = build_decode_panel(None, None, None, state="not_started")
    assert "Compile and step" in html
    assert source is None

    html, source = build_decode_panel(0, None, 0x1000, state="trap")
    assert "No instruction retired" in html
    assert "trap or interrupt" in html
    assert source is None


def test_r_type_shows_bits_register_names_and_meaning() -> None:
    html, source = decode_view(0x003100B3)
    attrs = [field["attr"] for field in source["reg"]]

    assert 'class="panel-context-band decode-context"' in html
    assert "ADD" in html
    assert "PC 0x00001000" in html
    assert "add ra, sp, gp" in html
    assert "ra (x1) &lt;- sp (x2) + gp (x3)" in html
    assert "rd x1/ra" in attrs
    assert "rs1 x2/sp" in attrs
    assert "rs2 x3/gp" in attrs
    assert source["reg"][-1]["name"] == "0000000"


def test_immediate_load_and_store_views() -> None:
    addi = ((-1 & 0xFFF) << 20) | (2 << 15) | (1 << 7) | 0b0010011
    html, source = decode_view(addi)
    assert "addi ra, sp, -1" in html
    assert "Immediate: -1 (0xffffffff)" in html
    assert source["reg"][-1]["name"] == "111111111111"

    lw = (8 << 20) | (2 << 15) | (2 << 12) | (10 << 7) | 0b0000011
    html, _ = decode_view(lw)
    assert "lw a0, 8(sp)" in html
    assert "memory32[sp (x2) + 8]" in html

    html, source = decode_view(s_type(12, 10, 2, 2))
    attrs = [field["attr"] for field in source["reg"]]
    assert "sw a0, 12(sp)" in html
    assert "memory32[sp (x2) + 12] &lt;- a0 (x10)" in html
    assert "imm[4:0]" in attrs
    assert "imm[11:5]" in attrs


def test_branch_and_jump_reconstruct_targets() -> None:
    html, source = decode_view(b_type(16, 0, 10, 0), pc=0x10014)
    attrs = [field["attr"] for field in source["reg"]]
    assert "beq a0, zero, +16" in html
    assert "target: 0x00010024" in html
    assert "imm[12]" in attrs
    assert "imm[11]" in attrs

    html, source = decode_view(j_type(-8, 1), pc=0x10020)
    assert "jal ra, -8" in html
    assert "target: 0x00010018" in html
    assert {"imm[20]", "imm[10:1]", "imm[11]", "imm[19:12]"}.issubset(
        {field["attr"] for field in source["reg"]}
    )


def test_upper_csr_system_and_m_extension_views() -> None:
    lui = (0x12345 << 12) | (5 << 7) | 0b0110111
    html, _ = decode_view(lui)
    assert "lui t0, 0x12345" in html
    assert "Upper immediate value: 0x12345000" in html

    csrrw = (0x340 << 20) | (11 << 15) | (1 << 12) | (10 << 7) | 0b1110011
    html, source = decode_view(csrrw)
    assert "csrrw a0, mscratch, a1" in html
    assert "CSR: mscratch (0x340)" in html
    assert source["reg"][-1]["attr"] == "csr[11:0]"

    html, _ = decode_view(0x00100073)
    assert "EBREAK" in html
    assert "halt at the breakpoint instruction" in html

    mul = (1 << 25) | (3 << 20) | (2 << 15) | (1 << 7) | 0b0110011
    html, _ = decode_view(mul)
    assert "R-Type / M" in html
    assert "mul ra, sp, gp" in html


@pytest.mark.parametrize(
    ("instruction", "mnemonic"),
    [
        (0x0040, "C.ADDI4SPN"),
        (0x4000, "C.LW"),
        (0xC008, "C.SW"),
        (0x0411, "C.ADDI"),
        (0x2001, "C.JAL"),
        (0x4089, "C.LI"),
        (0x6121, "C.ADDI16SP"),
        (0x628D, "C.LUI"),
        (0x8005, "C.SRLI"),
        (0x8405, "C.SRAI"),
        (0x883D, "C.ANDI"),
        (0x9C05, "C.SUB"),
        (0xA001, "C.J"),
        (0xC009, "C.BEQZ"),
        (0xE009, "C.BNEZ"),
        (0x008A, "C.SLLI"),
        (0x4092, "C.LWSP"),
        (0x8082, "C.JR"),
        (0x8192, "C.MV"),
        (0x9002, "C.EBREAK"),
        (0x9082, "C.JALR"),
        (0x9426, "C.ADD"),
        (0xC016, "C.SWSP"),
    ],
)
def test_supported_compressed_native_layouts(instruction: int, mnemonic: str) -> None:
    html, source = decode_view(instruction, width=2)
    assert mnemonic in html
    assert "16-bit" in html
    assert "Expands to:" in html
    assert source["config"]["bits"] == 16
    assert source["reg"][0]["attr"] == "quadrant"


def test_compressed_split_immediate_and_expansion() -> None:
    html, source = decode_view(0x0411, width=2)
    attrs = [field["attr"] for field in source["reg"]]
    assert "c.addi s0, 4" in html
    assert "Expands to: addi s0, s0, 4" in html
    assert "imm[4:0]" in attrs
    assert "imm[5]" in attrs

    html, source = decode_view(0x6121, width=2)
    attrs = [field["attr"] for field in source["reg"]]
    assert "C.ADDI16SP" in html
    assert {"nzimm[9]", "nzimm[8:7]", "nzimm[6]", "nzimm[5]", "nzimm[4]"}.issubset(attrs)


@pytest.mark.parametrize(("instruction", "width"), [(0xFFFFFFFF, 4), (0xFFFF, 2), (0x0000, 2)])
def test_unknown_and_reserved_encodings_are_intentional(instruction: int, width: int) -> None:
    html, source = decode_view(instruction, width=width)
    assert "Unsupported or reserved instruction encoding" in html
    assert any("invalid" in field["rect"]["class"] for field in source["reg"])
