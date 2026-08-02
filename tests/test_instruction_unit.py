from rv32i.cpu import Processor
from rv32i.memory import Memory
from rv32i.execution import (
    execute_instruction_rtype,
    execute_instruction_itype_imm,
    execute_instruction_itype_load,
    execute_instruction_itype_jalr,
    execute_instruction_stype,
    execute_instruction_btype,
    execute_instruction_utype,
    execute_instruction_jtype,
)


def u32(val):
    return val & 0xFFFFFFFF


class TestRType:
    def make(self, name, rd, rs1, rs2):
        return {
            "inst_type": "R-Type",
            "inst_name": name,
            "rd": rd,
            "rs1": rs1,
            "rs2": rs2,
        }

    def run(self, name, rs1_val, rs2_val, rd=3, rs1=1, rs2=2):
        proc = Processor()
        proc.write_register(rs1, rs1_val)
        proc.write_register(rs2, rs2_val)
        execute_instruction_rtype(self.make(name, rd, rs1, rs2), proc)
        return proc.read_register(rd)

    def test_add(self):
        assert self.run("add", 10, 20) == 30

    def test_add_overflow(self):
        assert self.run("add", 0xFFFFFFFF, 1) == 0

    def test_add_negative(self):
        assert self.run("add", 0xFFFFFFFE, 3) == 1

    def test_sub(self):
        assert self.run("sub", 20, 10) == 10

    def test_sub_underflow(self):
        assert self.run("sub", 0, 1) == 0xFFFFFFFF

    def test_xor(self):
        assert self.run("xor", 0xFF00FF00, 0x0F0F0F0F) == 0xF00FF00F

    def test_or(self):
        assert self.run("or", 0xFF00, 0x00FF) == 0xFFFF

    def test_and(self):
        assert self.run("and", 0xFF00, 0x0FF0) == 0x0F00

    def test_sll(self):
        assert self.run("sll", 1, 4) == 16

    def test_sll_mask_shift(self):
        assert self.run("sll", 1, 33) == 2

    def test_srl(self):
        assert self.run("srl", 0x80000000, 1) == 0x40000000

    def test_sra(self):
        assert self.run("sra", 0x80000000, 1) == 0xC0000000

    def test_slt_less(self):
        assert self.run("slt", 0xFFFFFFFF, 1) == 1

    def test_slt_equal(self):
        assert self.run("slt", 5, 5) == 0

    def test_slt_greater(self):
        assert self.run("slt", 10, 5) == 0

    def test_sltu_less(self):
        assert self.run("sltu", 1, 0xFFFFFFFF) == 1

    def test_sltu_equal(self):
        assert self.run("sltu", 5, 5) == 0

    def test_x0_always_zero(self):
        proc = Processor()
        proc.write_register(1, 42)
        proc.write_register(2, 58)
        execute_instruction_rtype(self.make("add", 0, 1, 2), proc)
        assert proc.read_register(0) == 0

    def test_sra_positive(self):
        assert self.run("sra", 0x40000000, 1) == 0x20000000


class TestITypeImm:
    def make(self, name, rd, rs1, imm):
        return {
            "inst_type": "I-Type",
            "inst_name": name,
            "rd": rd,
            "rs1": rs1,
            "imm": imm,
        }

    def run(self, name, rs1_val, imm, rd=3, rs1=1):
        proc = Processor()
        proc.write_register(rs1, rs1_val)
        execute_instruction_itype_imm(self.make(name, rd, rs1, imm), proc)
        return proc.read_register(rd)

    def test_addi(self):
        assert self.run("addi", 10, 5) == 15

    def test_addi_negative_imm(self):
        assert self.run("addi", 10, 0xFFC) == 6

    def test_xori(self):
        assert self.run("xori", 0xFF, 0x0F) == 0xF0

    def test_ori(self):
        assert self.run("ori", 0xF0, 0x0F) == 0xFF

    def test_andi(self):
        assert self.run("andi", 0xFF, 0x0F) == 0x0F

    def test_slli(self):
        assert self.run("slli", 1, 4) == 16

    def test_srli(self):
        assert self.run("srli", 0x80000000, 4) == 0x08000000

    def test_srai(self):
        assert self.run("srai", 0x80000000, 4) == 0xF8000000

    def test_slti_less(self):
        assert self.run("slti", 0xFFFFFFFF, 1) == 1

    def test_slti_greater(self):
        assert self.run("slti", 10, 5) == 0

    def test_sltiu_less(self):
        assert self.run("sltiu", 1, 10) == 1

    def test_addi_x0(self):
        proc = Processor()
        execute_instruction_itype_imm(self.make("addi", 3, 0, 42), proc)
        assert proc.read_register(3) == 42


class TestITypeLoad:
    def make(self, name, rd, rs1, imm):
        return {
            "inst_type": "I-Type",
            "inst_name": name,
            "rd": rd,
            "rs1": rs1,
            "imm": imm,
        }

    def test_lw(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_word(0x1000, 0xDEADBEEF)
        execute_instruction_itype_load(self.make("lw", 3, 1, 0), proc, mem)
        assert proc.read_register(3) == 0xDEADBEEF

    def test_lh_positive(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_halfword(0x1000, 0x7FFF)
        execute_instruction_itype_load(self.make("lh", 3, 1, 0), proc, mem)
        assert proc.read_register(3) == 0x7FFF

    def test_lh_negative(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_halfword(0x1000, 0xFFFF)
        execute_instruction_itype_load(self.make("lh", 3, 1, 0), proc, mem)
        assert proc.read_register(3) == 0xFFFFFFFF

    def test_lb_positive(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_byte(0x1000, 0x7F)
        execute_instruction_itype_load(self.make("lb", 3, 1, 0), proc, mem)
        assert proc.read_register(3) == 0x7F

    def test_lb_negative(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_byte(0x1000, 0xFF)
        execute_instruction_itype_load(self.make("lb", 3, 1, 0), proc, mem)
        assert proc.read_register(3) == 0xFFFFFFFF

    def test_lbu(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_byte(0x1000, 0xFF)
        execute_instruction_itype_load(self.make("lbu", 3, 1, 0), proc, mem)
        assert proc.read_register(3) == 0xFF

    def test_lhu(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_halfword(0x1000, 0xFFFF)
        execute_instruction_itype_load(self.make("lhu", 3, 1, 0), proc, mem)
        assert proc.read_register(3) == 0xFFFF

    def test_load_with_offset(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        mem.write_word(0x1004, 0x12345678)
        execute_instruction_itype_load(self.make("lw", 3, 1, 4), proc, mem)
        assert proc.read_register(3) == 0x12345678


class TestSType:
    def make(self, name, rs1, rs2, imm):
        return {
            "inst_type": "S-Type",
            "inst_name": name,
            "rs1": rs1,
            "rs2": rs2,
            "imm": imm,
        }

    def test_sw(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        proc.write_register(2, 0xDEADBEEF)
        execute_instruction_stype(self.make("sw", 1, 2, 0), proc, mem)
        assert mem.read_word(0x1000) == 0xDEADBEEF

    def test_sh(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        proc.write_register(2, 0x1234)
        execute_instruction_stype(self.make("sh", 1, 2, 0), proc, mem)
        assert mem.read_halfword(0x1000) == 0x1234

    def test_sb(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        proc.write_register(2, 0xAB)
        execute_instruction_stype(self.make("sb", 1, 2, 0), proc, mem)
        assert mem.read_byte(0x1000) == 0xAB

    def test_store_with_offset(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(1, 0x1000)
        proc.write_register(2, 0x42)
        execute_instruction_stype(self.make("sw", 1, 2, 8), proc, mem)
        assert mem.read_word(0x1008) == 0x42


class TestBType:
    def make(self, name, rs1, rs2, imm):
        return {
            "inst_type": "B-Type",
            "inst_name": name,
            "rs1": rs1,
            "rs2": rs2,
            "imm": imm,
        }

    def test_beq_taken(self):
        proc = Processor()
        proc.write_register(1, 10)
        proc.write_register(2, 10)
        execute_instruction_btype(self.make("beq", 1, 2, 8), proc, 0x100)
        assert proc.read_pc() == 0x108

    def test_beq_not_taken(self):
        proc = Processor()
        proc.set_pc(0x100)
        proc.write_register(1, 10)
        proc.write_register(2, 20)
        execute_instruction_btype(self.make("beq", 1, 2, 8), proc, 0x100)
        assert proc.read_pc() == 0x100

    def test_bne_taken(self):
        proc = Processor()
        proc.write_register(1, 10)
        proc.write_register(2, 20)
        execute_instruction_btype(self.make("bne", 1, 2, 8), proc, 0x100)
        assert proc.read_pc() == 0x108

    def test_blt_taken(self):
        proc = Processor()
        proc.write_register(1, 0xFFFFFFFF)
        proc.write_register(2, 1)
        execute_instruction_btype(self.make("blt", 1, 2, 8), proc, 0x100)
        assert proc.read_pc() == 0x108

    def test_bge_taken(self):
        proc = Processor()
        proc.write_register(1, 10)
        proc.write_register(2, 10)
        execute_instruction_btype(self.make("bge", 1, 2, 8), proc, 0x100)
        assert proc.read_pc() == 0x108

    def test_bltu_taken(self):
        proc = Processor()
        proc.write_register(1, 1)
        proc.write_register(2, 0xFFFFFFFF)
        execute_instruction_btype(self.make("bltu", 1, 2, 8), proc, 0x100)
        assert proc.read_pc() == 0x108

    def test_bgeu_taken(self):
        proc = Processor()
        proc.write_register(1, 0xFFFFFFFF)
        proc.write_register(2, 1)
        execute_instruction_btype(self.make("bgeu", 1, 2, 8), proc, 0x100)
        assert proc.read_pc() == 0x108

    def test_branch_backward(self):
        proc = Processor()
        proc.write_register(1, 5)
        proc.write_register(2, 5)
        execute_instruction_btype(self.make("beq", 1, 2, -8), proc, 0x100)
        assert proc.read_pc() == 0xF8


class TestUType:
    def make(self, name, rd, imm_31_12):
        return {
            "inst_type": "U-Type",
            "inst_name": name,
            "rd": rd,
            "imm_31_12": imm_31_12,
        }

    def test_lui(self):
        proc = Processor()
        execute_instruction_utype(self.make("lui", 1, 0x12345), proc)
        assert proc.read_register(1) == 0x12345000

    def test_auipc(self):
        proc = Processor()
        proc.set_pc(0x1000)
        execute_instruction_utype(self.make("auipc", 1, 0x10), proc)
        assert proc.read_register(1) == 0x11000


class TestJType:
    def make(self, name, rd, imm):
        return {
            "inst_type": "J-Type",
            "inst_name": name,
            "rd": rd,
            "imm": imm,
        }

    def test_jal(self):
        proc = Processor()
        proc.set_pc(0x1000)
        execute_instruction_jtype(self.make("jal", 1, 0x20), proc, 0x1000)
        assert proc.read_register(1) == 0x1004
        assert proc.read_pc() == 0x1020

    def test_jal_negative_offset(self):
        proc = Processor()
        proc.set_pc(0x1000)
        execute_instruction_jtype(self.make("jal", 1, -8), proc, 0x1000)
        assert proc.read_register(1) == 0x1004
        assert proc.read_pc() == 0x0FF8


class TestJALR:
    def make(self, name, rd, rs1, imm):
        return {
            "inst_type": "I-Type",
            "inst_name": name,
            "rd": rd,
            "rs1": rs1,
            "imm": imm,
        }

    def test_jalr(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.write_register(1, 0x2000)
        execute_instruction_itype_jalr(self.make("jalr", 2, 1, 0), proc)
        assert proc.read_register(2) == 0x1004
        assert proc.read_pc() == 0x2000

    def test_jalr_clear_lsb(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.write_register(1, 0x2001)
        execute_instruction_itype_jalr(self.make("jalr", 2, 1, 0), proc)
        assert proc.read_pc() == 0x2000

    def test_jalr_with_offset(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.write_register(1, 0x2000)
        execute_instruction_itype_jalr(self.make("jalr", 2, 1, 4), proc)
        assert proc.read_pc() == 0x2004
