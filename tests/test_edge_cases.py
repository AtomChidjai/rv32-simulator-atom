import pytest

from rv32i.cpu import Processor
from rv32i.decoder import Decoder
from rv32i.memory import Memory
from rv32i.execution import (
    execute_instruction_rtype,
    execute_instruction_itype_imm,
    execute_instruction_itype_load,
    execute_instruction_btype,
    execute_instruction_itype_jalr,
)


class TestX0Hardwired:
    def test_rtype_writes_x0_ignored(self):
        proc = Processor()
        proc.write_register(1, 10)
        proc.write_register(2, 20)
        decoded = {
            "inst_type": "R-Type",
            "inst_name": "add",
            "rd": 0,
            "rs1": 1,
            "rs2": 2,
        }
        execute_instruction_rtype(decoded, proc)
        assert proc.read_register(0) == 0

    def test_itype_writes_x0_ignored(self):
        proc = Processor()
        proc.write_register(1, 10)
        decoded = {
            "inst_type": "I-Type",
            "inst_name": "addi",
            "rd": 0,
            "rs1": 1,
            "imm": 42,
        }
        execute_instruction_itype_imm(decoded, proc)
        assert proc.read_register(0) == 0

    def test_x0_source_is_zero(self):
        proc = Processor()
        decoded = {
            "inst_type": "R-Type",
            "inst_name": "add",
            "rd": 3,
            "rs1": 0,
            "rs2": 0,
        }
        execute_instruction_rtype(decoded, proc)
        assert proc.read_register(3) == 0


class TestShiftMasking:
    def test_sll_mask_5bits(self):
        proc = Processor()
        proc.write_register(1, 1)
        proc.write_register(2, 33)
        decoded = {
            "inst_type": "R-Type",
            "inst_name": "sll",
            "rd": 3,
            "rs1": 1,
            "rs2": 2,
        }
        execute_instruction_rtype(decoded, proc)
        assert proc.read_register(3) == 2

    def test_srl_mask_5bits(self):
        proc = Processor()
        proc.write_register(1, 4)
        proc.write_register(2, 33)
        decoded = {
            "inst_type": "R-Type",
            "inst_name": "srl",
            "rd": 3,
            "rs1": 1,
            "rs2": 2,
        }
        execute_instruction_rtype(decoded, proc)
        assert proc.read_register(3) == 2

    def test_slli_mask_5bits(self):
        proc = Processor()
        proc.write_register(1, 1)
        decoded = {
            "inst_type": "I-Type",
            "inst_name": "slli",
            "rd": 3,
            "rs1": 1,
            "imm": 33,
        }
        execute_instruction_itype_imm(decoded, proc)
        assert proc.read_register(3) == 2


class TestShiftImmediateEncoding:
    @pytest.mark.parametrize("funct3", [0b001, 0b101])
    def test_rv32_shift_with_nonzero_imm_bit_11_is_illegal(self, funct3):
        instruction = (0b1000000 << 25) | (1 << 20) | (1 << 15) | (funct3 << 12) | (2 << 7) | 0b0010011
        assert Decoder().decoding(instruction)["inst_name"] == "unknown"


class TestSignExtension:
    def test_addi_sign_extend_negative(self):
        proc = Processor()
        proc.write_register(1, 0)
        decoded = {
            "inst_type": "I-Type",
            "inst_name": "addi",
            "rd": 3,
            "rs1": 1,
            "imm": 0xFFF,
        }
        execute_instruction_itype_imm(decoded, proc)
        assert proc.read_register(3) == 0xFFFFFFFF

    def test_addi_sign_extend_positive(self):
        proc = Processor()
        proc.write_register(1, 0)
        decoded = {
            "inst_type": "I-Type",
            "inst_name": "addi",
            "rd": 3,
            "rs1": 1,
            "imm": 0x7FF,
        }
        execute_instruction_itype_imm(decoded, proc)
        assert proc.read_register(3) == 0x7FF

    def test_lb_sign_extend_0x80(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_byte(0x1000, 0x80)
        decoded = {
            "inst_type": "I-Type",
            "inst_name": "lb",
            "rd": 3,
            "rs1": 1,
            "imm": 0,
        }
        execute_instruction_itype_load(decoded, proc, mem)
        assert proc.read_register(3) == 0xFFFFFF80

    def test_lh_sign_extend_0x8000(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_halfword(0x1000, 0x8000)
        decoded = {
            "inst_type": "I-Type",
            "inst_name": "lh",
            "rd": 3,
            "rs1": 1,
            "imm": 0,
        }
        execute_instruction_itype_load(decoded, proc, mem)
        assert proc.read_register(3) == 0xFFFF8000


class TestBranchEdgeCases:
    def test_beq_not_taken_different(self):
        proc = Processor()
        proc.set_pc(0x100)
        proc.write_register(1, 1)
        proc.write_register(2, 2)
        decoded = {
            "inst_type": "B-Type",
            "inst_name": "beq",
            "rs1": 1,
            "rs2": 2,
            "imm": 8,
        }
        execute_instruction_btype(decoded, proc, 0x100)
        assert proc.read_pc() == 0x100

    def test_blt_signed_comparison(self):
        proc = Processor()
        proc.write_register(1, 0xFFFFFFFF)
        proc.write_register(2, 1)
        decoded = {
            "inst_type": "B-Type",
            "inst_name": "blt",
            "rs1": 1,
            "rs2": 2,
            "imm": 8,
        }
        execute_instruction_btype(decoded, proc, 0x100)
        assert proc.read_pc() == 0x108

    def test_bltu_unsigned_comparison(self):
        proc = Processor()
        proc.set_pc(0x100)
        proc.write_register(1, 0xFFFFFFFF)
        proc.write_register(2, 1)
        decoded = {
            "inst_type": "B-Type",
            "inst_name": "bltu",
            "rs1": 1,
            "rs2": 2,
            "imm": 8,
        }
        execute_instruction_btype(decoded, proc, 0x100)
        assert proc.read_pc() == 0x100


class TestJumpEdgeCases:
    def test_jalr_clears_lsb(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.write_register(1, 0x2001)
        decoded = {
            "inst_type": "I-Type",
            "inst_name": "jalr",
            "rd": 2,
            "rs1": 1,
            "imm": 0,
        }
        execute_instruction_itype_jalr(decoded, proc)
        assert proc.read_pc() == 0x2000

    def test_jalr_with_negative_offset(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.write_register(1, 0x2000)
        decoded = {
            "inst_type": "I-Type",
            "inst_name": "jalr",
            "rd": 2,
            "rs1": 1,
            "imm": 0xFFC,
        }
        execute_instruction_itype_jalr(decoded, proc)
        assert proc.read_pc() == 0x1FFC


class TestMemoryAlignment:
    def test_word_read_write(self):
        mem = Memory()
        mem.write_word(0x1000, 0xDEADBEEF)
        assert mem.read_word(0x1000) == 0xDEADBEEF

    def test_halfword_read_write(self):
        mem = Memory()
        mem.write_halfword(0x1000, 0x1234)
        assert mem.read_halfword(0x1000) == 0x1234

    def test_byte_read_write(self):
        mem = Memory()
        mem.write_byte(0x1000, 0xAB)
        assert mem.read_byte(0x1000) == 0xAB

    def test_halfword_overwrite_low(self):
        mem = Memory()
        mem.write_word(0x1000, 0xFFFFFFFF)
        mem.write_halfword(0x1000, 0x0000)
        assert mem.read_word(0x1000) == 0xFFFF0000

    def test_byte_overwrite(self):
        mem = Memory()
        mem.write_word(0x1000, 0xFFFFFFFF)
        mem.write_byte(0x1000, 0x00)
        assert mem.read_word(0x1000) == 0xFFFFFF00
