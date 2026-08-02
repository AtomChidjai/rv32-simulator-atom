from rv32i.cpu import Processor
from rv32i.memory import Memory
from rv32i.decoder import Decoder
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


class TestFetchInstruction:
    def test_32bit_instruction(self):
        mem = Memory()
        mem.write_word(0x1000, 0x00310093)
        inst, size = mem.fetch_instruction(0x1000)
        assert size == 4
        assert inst == 0x00310093

    def test_16bit_instruction(self):
        mem = Memory()
        mem.write_halfword(0x1000, 0x0001)  # C.NOP
        inst, size = mem.fetch_instruction(0x1000)
        assert size == 2
        assert inst == 0x0001

    def test_mixed_16_and_32(self):
        mem = Memory()
        mem.write_halfword(0x1000, 0x0001)  # 16-bit C.NOP
        mem.write_word(0x1004, 0x00310093)  # 32-bit
        inst1, size1 = mem.fetch_instruction(0x1000)
        assert size1 == 2
        inst2, size2 = mem.fetch_instruction(0x1004)
        assert size2 == 4

    def test_2byte_alignment(self):
        mem = Memory()
        mem.write_halfword(0x1002, 0x0001)
        inst, size = mem.fetch_instruction(0x1002)
        assert size == 2


class TestIncrementPC:
    def test_default_size(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.increment_pc()
        assert proc.read_pc() == 0x1004

    def test_size_2(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.increment_pc(2)
        assert proc.read_pc() == 0x1002

    def test_size_4(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.increment_pc(4)
        assert proc.read_pc() == 0x1004


class TestDecodeCompressedC0:
    def setup_method(self):
        self.dec = Decoder()

    def test_c_addi4spn(self):
        # C.ADDI4SPN x8, sp, 4
        d = self.dec.decode_compressed(0x0040)
        assert d["inst_name"] == "addi"
        assert d["inst_type"] == "I-Type"
        assert d["rd"] == 8
        assert d["rs1"] == 2
        assert d["imm"] == 4

    def test_c_addi4spn_reserved(self):
        d = self.dec.decode_compressed(0x0000)
        assert d["inst_name"] == "reserved"

    def test_c_lw(self):
        # C.LW x10, 0(x8)
        d = self.dec.decode_compressed(0x4008)
        assert d["inst_name"] == "lw"
        assert d["inst_type"] == "I-Type"
        assert d["rd"] == 10
        assert d["rs1"] == 8
        assert d["imm"] == 0

    def test_c_sw(self):
        # C.SW x10, 0(x8)
        d = self.dec.decode_compressed(0xC008)
        assert d["inst_name"] == "sw"
        assert d["inst_type"] == "S-Type"
        assert d["rs1"] == 8
        assert d["rs2"] == 10


class TestDecodeCompressedC1:
    def setup_method(self):
        self.dec = Decoder()

    def test_c_nop(self):
        d = self.dec.decode_compressed(0x0001)
        assert d["inst_name"] == "nop"
        assert d["rd"] == 0

    def test_c_addi(self):
        # C.ADDI x8, 4
        d = self.dec.decode_compressed(0x0411)
        assert d["inst_name"] == "addi"
        assert d["rd"] == 8
        assert d["rs1"] == 8
        assert d["imm"] == 4

    def test_c_li(self):
        # C.LI x1, 2
        d = self.dec.decode_compressed(0x4089)
        assert d["inst_name"] == "addi"
        assert d["rd"] == 1
        assert d["rs1"] == 0
        assert d["imm"] == 2

    def test_c_lui(self):
        # C.LUI x5, 3
        d = self.dec.decode_compressed(0x628D)
        assert d["inst_name"] == "lui"
        assert d["inst_type"] == "U-Type"
        assert d["rd"] == 5

    def test_c_addi16sp(self):
        # C.ADDI16SP sp, 64
        d = self.dec.decode_compressed(0x6121)
        assert d["inst_name"] == "addi"
        assert d["rd"] == 2
        assert d["rs1"] == 2
        assert d["imm"] == 64

    def test_c_j(self):
        # C.J offset=0
        d = self.dec.decode_compressed(0xA001)
        assert d["inst_name"] == "jal"
        assert d["inst_type"] == "J-Type"
        assert d["rd"] == 0

    def test_c_j_positive_offset(self):
        # Assembled encoding for C.J +16.
        d = self.dec.decode_compressed(0xA801)
        assert d["inst_name"] == "jal"
        assert d["imm"] == 16

    def test_c_jal(self):
        # C.JAL offset=0 (RV32 only)
        d = self.dec.decode_compressed(0x2001)
        assert d["inst_name"] == "jal"
        assert d["inst_type"] == "J-Type"
        assert d["rd"] == 1

    def test_c_beqz(self):
        # C.BEQZ x8, offset=2
        d = self.dec.decode_compressed(0xC009)
        assert d["inst_name"] == "beq"
        assert d["inst_type"] == "B-Type"
        assert d["rs1"] == 8
        assert d["rs2"] == 0
        assert d["imm"] == 2

    def test_c_bnez(self):
        # C.BNEZ x8, offset=2
        d = self.dec.decode_compressed(0xE009)
        assert d["inst_name"] == "bne"
        assert d["inst_type"] == "B-Type"
        assert d["rs1"] == 8
        assert d["rs2"] == 0
        assert d["imm"] == 2

    def test_c_srli(self):
        # C.SRLI x8, 1
        d = self.dec.decode_compressed(0x8005)
        assert d["inst_name"] == "srli"
        assert d["inst_type"] == "I-Type"
        assert d["rd"] == 8
        assert d["rs1"] == 8
        assert d["imm"] == 1

    def test_c_srai(self):
        # C.SRAI x8, 1
        d = self.dec.decode_compressed(0x8405)
        assert d["inst_name"] == "srai"
        assert d["inst_type"] == "I-Type"
        assert d["rd"] == 8

    def test_c_andi(self):
        # C.ANDI x8, -1
        d = self.dec.decode_compressed(0x987D)
        assert d["inst_name"] == "andi"
        assert d["inst_type"] == "I-Type"
        assert d["rd"] == 8
        assert d["imm"] == 0xFFF  # unsigned 12-bit, sign-extends to -1 in execution

    def test_c_sub(self):
        # C.SUB x8, x9
        d = self.dec.decode_compressed(0x9C05)
        assert d["inst_name"] == "sub"
        assert d["inst_type"] == "R-Type"
        assert d["rd"] == 8
        assert d["rs1"] == 8
        assert d["rs2"] == 9

    def test_c_xor(self):
        # C.XOR x8, x9
        d = self.dec.decode_compressed(0x9C25)
        assert d["inst_name"] == "xor"
        assert d["inst_type"] == "R-Type"

    def test_c_or(self):
        # C.OR x8, x9
        d = self.dec.decode_compressed(0x9C45)
        assert d["inst_name"] == "or"
        assert d["inst_type"] == "R-Type"

    def test_c_and(self):
        # C.AND x8, x9
        d = self.dec.decode_compressed(0x9C65)
        assert d["inst_name"] == "and"
        assert d["inst_type"] == "R-Type"


class TestDecodeCompressedC2:
    def setup_method(self):
        self.dec = Decoder()

    def test_c_slli(self):
        # C.SLLI x1, 2
        d = self.dec.decode_compressed(0x008A)
        assert d["inst_name"] == "slli"
        assert d["inst_type"] == "I-Type"
        assert d["rd"] == 1
        assert d["rs1"] == 1
        assert d["imm"] == 2

    def test_c_lwsp_rd_zero_is_reserved(self):
        assert self.dec.decode_compressed(0x4002)["inst_name"] == "reserved"

    def test_c_lui_rd_zero_is_reserved(self):
        assert self.dec.decode_compressed(0x6005)["inst_name"] == "reserved"

    def test_c_lwsp(self):
        # C.LWSP x1, 4(sp)
        d = self.dec.decode_compressed(0x4092)
        assert d["inst_name"] == "lw"
        assert d["inst_type"] == "I-Type"
        assert d["rd"] == 1
        assert d["rs1"] == 2
        assert d["imm"] == 4

    def test_c_jr(self):
        # C.JR x1
        d = self.dec.decode_compressed(0x8082)
        assert d["inst_name"] == "jalr"
        assert d["rd"] == 0
        assert d["rs1"] == 1
        assert d["imm"] == 0

    def test_c_mv(self):
        # C.MV x3, x4
        d = self.dec.decode_compressed(0x8192)
        assert d["inst_name"] == "add"
        assert d["inst_type"] == "R-Type"
        assert d["rd"] == 3
        assert d["rs1"] == 0
        assert d["rs2"] == 4

    def test_c_ebreak(self):
        d = self.dec.decode_compressed(0x9002)
        assert d["inst_name"] == "ebreak"

    def test_c_jalr(self):
        # C.JALR x1
        d = self.dec.decode_compressed(0x9082)
        assert d["inst_name"] == "jalr"
        assert d["rd"] == 1
        assert d["rs1"] == 1

    def test_c_add(self):
        # C.ADD x8, x9
        d = self.dec.decode_compressed(0x9426)
        assert d["inst_name"] == "add"
        assert d["inst_type"] == "R-Type"
        assert d["rd"] == 8
        assert d["rs1"] == 8
        assert d["rs2"] == 9

    def test_c_swsp(self):
        # C.SWSP x2, 0(sp)
        d = self.dec.decode_compressed(0xC00A)
        assert d["inst_name"] == "sw"
        assert d["inst_type"] == "S-Type"
        assert d["rs1"] == 2
        assert d["rs2"] == 2


class TestCompressedRegisterMapping:
    def setup_method(self):
        self.dec = Decoder()

    def test_c_reg_x8(self):
        assert self.dec.c_reg(0) == 8

    def test_c_reg_x15(self):
        assert self.dec.c_reg(7) == 15

    def test_c_reg_range(self):
        for i in range(8):
            assert self.dec.c_reg(i) == i + 8


class TestFormatCompressed:
    def test_format(self):
        dec = Decoder()
        result = dec.format_compressed(0x0411)
        assert "addi" in result


class TestCompressedImmediateHelpers:
    def test_build_cj_imm(self):
        dec = Decoder()
        imm = dec.build_cj_imm(0xA001)
        assert isinstance(imm, int)

    def test_build_cb_imm(self):
        dec = Decoder()
        imm = dec.build_cb_imm(0xC005)
        assert isinstance(imm, int)


class TestCompressedExecutionIntegration:
    def test_c_addi_execution(self):
        proc = Processor()
        proc.write_register(8, 10)
        dec = Decoder()
        d = dec.decode_compressed(0x0411)  # C.ADDI x8, 4
        assert d["inst_name"] == "addi"
        execute_instruction_itype_imm(d, proc)
        assert proc.read_register(8) == 14

    def test_c_li_execution(self):
        proc = Processor()
        dec = Decoder()
        d = dec.decode_compressed(0x4089)  # C.LI x1, 2
        assert d["inst_name"] == "addi"
        assert d["rs1"] == 0
        execute_instruction_itype_imm(d, proc)
        assert proc.read_register(1) == 2

    def test_c_lui_execution(self):
        proc = Processor()
        dec = Decoder()
        d = dec.decode_compressed(0x628D)  # C.LUI x5, 3
        assert d["inst_name"] == "lui"
        execute_instruction_utype(d, proc)
        assert proc.read_register(5) == 0x3000

    def test_c_add_execution(self):
        proc = Processor()
        proc.write_register(8, 10)
        proc.write_register(9, 20)
        dec = Decoder()
        d = dec.decode_compressed(0x9426)  # C.ADD x8, x9
        assert d["inst_name"] == "add"
        execute_instruction_rtype(d, proc)
        assert proc.read_register(8) == 30

    def test_c_sub_execution(self):
        proc = Processor()
        proc.write_register(8, 20)
        proc.write_register(9, 5)
        dec = Decoder()
        d = dec.decode_compressed(0x9C05)  # C.SUB x8, x9
        assert d["inst_name"] == "sub"
        execute_instruction_rtype(d, proc)
        assert proc.read_register(8) == 15

    def test_c_lw_execution(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(8, 0x1000)
        mem.write_word(0x1000, 0xDEADBEEF)
        dec = Decoder()
        d = dec.decode_compressed(0x4000)  # C.LW x8, 0(x8)
        assert d["inst_name"] == "lw"
        execute_instruction_itype_load(d, proc, mem)
        assert proc.read_register(8) == 0xDEADBEEF

    def test_c_sw_execution(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(8, 0x1000)
        proc.write_register(10, 0x42)
        dec = Decoder()
        d = dec.decode_compressed(0xC008)  # C.SW x10, 0(x8)
        assert d["inst_name"] == "sw"
        execute_instruction_stype(d, proc, mem)
        assert mem.read_word(0x1000) == 0x42

    def test_c_beqz_taken(self):
        proc = Processor()
        proc.write_register(8, 0)
        dec = Decoder()
        d = dec.decode_compressed(0xC009)  # C.BEQZ x8, offset=2
        assert d["inst_name"] == "beq"
        execute_instruction_btype(d, proc, 0x1000)
        assert proc.read_pc() == 0x1002

    def test_c_bnez_taken(self):
        proc = Processor()
        proc.write_register(8, 1)
        dec = Decoder()
        d = dec.decode_compressed(0xE009)  # C.BNEZ x8, offset=2
        assert d["inst_name"] == "bne"
        execute_instruction_btype(d, proc, 0x1000)
        assert proc.read_pc() == 0x1002

    def test_c_jal_link_address(self):
        proc = Processor()
        dec = Decoder()
        d = dec.decode_compressed(0x2001)  # C.JAL offset=0
        d["_inst_size"] = 2
        execute_instruction_jtype(d, proc, 0x1000)
        assert proc.read_register(1) == 0x1002  # pc + 2

    def test_c_j_link_address(self):
        proc = Processor()
        dec = Decoder()
        d = dec.decode_compressed(0xA001)  # C.J offset=0
        d["_inst_size"] = 2
        execute_instruction_jtype(d, proc, 0x1000)
        assert proc.read_register(0) == 0

    def test_c_jalr_link_address(self):
        proc = Processor()
        proc.set_pc(0x1000)
        proc.write_register(1, 0x2000)
        dec = Decoder()
        d = dec.decode_compressed(0x9082)  # C.JALR x1
        d["_inst_size"] = 2
        execute_instruction_itype_jalr(d, proc)
        assert proc.read_register(1) == 0x1002  # pc + 2
        assert proc.read_pc() == 0x2000

    def test_c_mv_execution(self):
        proc = Processor()
        proc.write_register(4, 42)
        dec = Decoder()
        d = dec.decode_compressed(0x8192)  # C.MV x3, x4
        assert d["inst_name"] == "add"
        execute_instruction_rtype(d, proc)
        assert proc.read_register(3) == 42

    def test_c_slli_execution(self):
        proc = Processor()
        proc.write_register(1, 3)
        dec = Decoder()
        d = dec.decode_compressed(0x008A)  # C.SLLI x1, 2
        assert d["inst_name"] == "slli"
        execute_instruction_itype_imm(d, proc)
        assert proc.read_register(1) == 12

    def test_c_lwsp_execution(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(2, 0x1000)  # sp
        mem.write_word(0x1004, 0xABCD1234)
        dec = Decoder()
        d = dec.decode_compressed(0x4092)  # C.LWSP x1, 4(sp)
        assert d["inst_name"] == "lw"
        assert d["imm"] == 4
        execute_instruction_itype_load(d, proc, mem)
        assert proc.read_register(1) == 0xABCD1234

    def test_c_swsp_execution(self):
        proc = Processor()
        mem = Memory()
        proc.write_register(2, 0x1000)  # sp
        proc.write_register(5, 0x55)
        dec = Decoder()
        d = dec.decode_compressed(0xC016)  # C.SWSP x5, 0(sp)
        assert d["inst_name"] == "sw"
        assert d["rs2"] == 5
        execute_instruction_stype(d, proc, mem)
        assert mem.read_word(0x1000) == 0x55

    def test_c_andi_execution(self):
        proc = Processor()
        proc.write_register(8, 0xFF00)
        dec = Decoder()
        d = dec.decode_compressed(0x883D)  # C.ANDI x8, 15
        assert d["inst_name"] == "andi"
        execute_instruction_itype_imm(d, proc)
        assert proc.read_register(8) == 0

    def test_c_xor_execution(self):
        proc = Processor()
        proc.write_register(8, 0xFF00)
        proc.write_register(9, 0x0FF0)
        dec = Decoder()
        d = dec.decode_compressed(0x9C25)  # C.XOR x8, x9
        assert d["inst_name"] == "xor"
        execute_instruction_rtype(d, proc)
        assert proc.read_register(8) == 0xF0F0

    def test_c_or_execution(self):
        proc = Processor()
        proc.write_register(8, 0xF0F0)
        proc.write_register(9, 0x0F0F)
        dec = Decoder()
        d = dec.decode_compressed(0x9C45)  # C.OR x8, x9
        assert d["inst_name"] == "or"
        execute_instruction_rtype(d, proc)
        assert proc.read_register(8) == 0xFFFF

    def test_c_and_execution(self):
        proc = Processor()
        proc.write_register(8, 0xFFFF)
        proc.write_register(9, 0x00FF)
        dec = Decoder()
        d = dec.decode_compressed(0x9C65)  # C.AND x8, x9
        assert d["inst_name"] == "and"
        execute_instruction_rtype(d, proc)
        assert proc.read_register(8) == 0x00FF

    def test_c_addi_negative(self):
        proc = Processor()
        proc.write_register(8, 10)
        dec = Decoder()
        d = dec.decode_compressed(0x147D)  # C.ADDI x8, -1
        assert d["inst_name"] == "addi"
        execute_instruction_itype_imm(d, proc)
        assert proc.read_register(8) == 9

    def test_c_addi4spn_execution(self):
        proc = Processor()
        proc.write_register(2, 0x1000)  # sp
        dec = Decoder()
        d = dec.decode_compressed(0x0040)  # C.ADDI4SPN x8, sp, 4
        assert d["inst_name"] == "addi"
        assert d["rd"] == 8
        assert d["rs1"] == 2
        assert d["imm"] == 4
        execute_instruction_itype_imm(d, proc)
        assert proc.read_register(8) == 0x1004
