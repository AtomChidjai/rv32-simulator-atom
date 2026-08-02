"""Decode 16-bit RV32C and 32-bit RV32IM + Zicsr instructions."""

import sys
from .constants import (
    INSTRUCTION_TYPE,
    ITYPE_FUNCT3_IMM,
    RTYPE_FUNCT3_FUNCT7,
    ENV_IMM,
    FUNCT3_CSR,
    FUNCT3_LOAD,
    FUNCT3_JALR,
    FUNCT3_STYPE,
    FUNCT3_BTYPE,
)

def dbg(msg: str) -> None:
    print(msg, file=sys.stderr)

class Decoder:
    def __init__(self, verbose=False) -> None:
        self.verbose = verbose

    def parse_fields(self, inst: int) -> dict:
        """Extract every raw bitfield from a 32-bit instruction word."""
        opcode = inst & 0x7F
        rd = (inst >> 7) & 0x1F
        funct3 = (inst >> 12) & 0x07
        rs1 = (inst >> 15) & 0x1F
        rs2 = (inst >> 20) & 0x1F
        funct7 = (inst >> 25) & 0x7F
        imm_i = (inst >> 20) & 0xFFF
        imm4_0 = (inst >> 7) & 0x1F
        imm11_5 = (inst >> 25) & 0x7F
        imm4_1_11 = (inst >> 7) & 0x1F
        imm12_10_5 = (inst >> 25) & 0x7F
        raw_jal = (inst >> 7) & 0x1FFFFFF
        imm_31_12 = ((inst >> 7) & 0x1FFFFFF) >> 5
        return {
            "opcode": opcode, "rd": rd, "funct3": funct3,
            "rs1": rs1, "rs2": rs2, "funct7": funct7,
            "imm_i": imm_i, "imm4_0": imm4_0, "imm11_5": imm11_5,
            "imm4_1_11": imm4_1_11, "imm12_10_5": imm12_10_5,
            "raw_jal": raw_jal, "imm_31_12": imm_31_12,
        }

    def get_inst_type(self, opcode):
        """Map a 7-bit opcode to its instruction-type string (R/I/S/B/U/J)."""
        if opcode == INSTRUCTION_TYPE["OP_R"]:
            return "R-Type"
        elif opcode in (
            INSTRUCTION_TYPE["OP_I_IMM"],
            INSTRUCTION_TYPE["OP_I_LOAD"],
            INSTRUCTION_TYPE["OP_I_JALR"],
            INSTRUCTION_TYPE["OP_I_ENV"],
        ):
            return "I-Type"
        elif opcode == INSTRUCTION_TYPE["OP_S"]:
            return "S-Type"
        elif opcode == INSTRUCTION_TYPE["OP_B"]:
            return "B-Type"
        elif opcode == INSTRUCTION_TYPE["OP_J"]:
            return "J-Type"
        elif opcode in (
            INSTRUCTION_TYPE["OP_U_LUI"],
            INSTRUCTION_TYPE["OP_U_AUIPC"],
        ):
            return "U-Type"
        return "unknown"

    def get_inst_name(self, opcode, funct3, funct7, imm):
        """Resolve the mnemonic from opcode + funct3/funct7 (or ENV imm).

        Returns the lower-case mnemonic (e.g. ``"add"``, ``"lw"``, ``"csrrw"``)
        or ``"unknown"`` if the encoding is not recognized."""
        if opcode == INSTRUCTION_TYPE["OP_R"]:
            for inst_name, codes in RTYPE_FUNCT3_FUNCT7.items():
                if codes[0] == funct3 and codes[1] == funct7:
                    return inst_name

        elif opcode == INSTRUCTION_TYPE["OP_I_IMM"]:
            imm5_11 = (imm >> 5) & 0x7F
            for inst_name, codes in ITYPE_FUNCT3_IMM.items():
                if codes[0] != funct3:
                    continue
                if inst_name in ("slli", "srli", "srai"):
                    if codes[1] == imm5_11:
                        return inst_name
                else:
                    return inst_name

        elif opcode == INSTRUCTION_TYPE["OP_I_LOAD"]:
            return FUNCT3_LOAD.get(funct3, "unknown")

        elif opcode == INSTRUCTION_TYPE["OP_I_JALR"]:
            return FUNCT3_JALR.get(funct3, "unknown")

        elif opcode == INSTRUCTION_TYPE["OP_I_ENV"]:
            if funct3 == 0:
                env_names = {v: k for k, v in ENV_IMM.items()}
                return env_names.get(imm, "unknown")
            return FUNCT3_CSR.get(funct3, "unknown")

        elif opcode == INSTRUCTION_TYPE["OP_S"]:
            return FUNCT3_STYPE.get(funct3, "unknown")

        elif opcode == INSTRUCTION_TYPE["OP_B"]:
            return FUNCT3_BTYPE.get(funct3, "unknown")

        elif opcode == INSTRUCTION_TYPE["OP_U_LUI"]:
            return "lui"

        elif opcode == INSTRUCTION_TYPE["OP_U_AUIPC"]:
            return "auipc"

        elif opcode == INSTRUCTION_TYPE["OP_J"]:
            return "jal"

        return "unknown"

    @staticmethod
    def sign_extend(value: int, bits: int) -> int:
        sign_bit = 1 << (bits - 1)
        return (value & (sign_bit - 1)) - (value & sign_bit)

    def build_s_imm(self, f: dict) -> int:
        imm = (f["imm11_5"] << 5) | f["imm4_0"]
        return self.sign_extend(imm, 12)

    def build_b_imm(self, f: dict) -> int:
        imm4_1 = (f["imm4_1_11"] >> 1) & 0xF
        imm10_5 = f["imm12_10_5"] & 0x3F
        imm11 = f["imm4_1_11"] & 1
        imm12 = (f["imm12_10_5"] >> 6) & 1
        imm = (imm12 << 12) | (imm11 << 11) | (imm10_5 << 5) | (imm4_1 << 1)
        return self.sign_extend(imm, 13)

    def build_j_imm(self, f: dict) -> int:
        raw = f["raw_jal"]
        imm = ((raw >> 24) & 0x1) << 20 \
            | ((raw >> 5)  & 0xFF) << 12 \
            | ((raw >> 13) & 0x1)  << 11 \
            | ((raw >> 14) & 0x3FF) << 1
        return self.sign_extend(imm, 21)

    def format_instruction(self, inst: int) -> str:
        inst_hex = f"0x{inst:08x}"
        f = self.parse_fields(inst)
        opcode, rd, funct3 = f["opcode"], f["rd"], f["funct3"]
        rs1, rs2, funct7 = f["rs1"], f["rs2"], f["funct7"]
        imm_i = f["imm_i"]
        imm4_0, imm11_5 = f["imm4_0"], f["imm11_5"]
        imm4_1_11, imm12_10_5 = f["imm4_1_11"], f["imm12_10_5"]

        bin_opcode = f"{opcode:07b}"
        bin_rd = f"{rd:05b}"
        bin_funct3 = f"{funct3:03b}"
        bin_rs1 = f"{rs1:05b}"
        bin_rs2 = f"{rs2:05b}"
        bin_funct7 = f"{funct7:07b}"
        bin_imm = f"{imm_i:012b}"
        bin_imm4_0 = f"{imm4_0:05b}"
        bin_imm11_5 = f"{imm11_5:07b}"
        bin_imm4_1_11 = f"{imm4_1_11:05b}"
        bin_imm12_10_5 = f"{imm12_10_5:07b}"
        bin_imm_jal = f"{self.build_j_imm(f):020b}"
        bin_imm_31_12 = f"{f['imm_31_12']:020b}"

        inst_name = self.get_inst_name(opcode, funct3, funct7, imm_i)
        inst_type = self.get_inst_type(opcode)

        if inst_name in FUNCT3_CSR.values() or inst_name == "mret":
            inst_type = "CSR-Type"

        lines = []
        lines.append("=" * 90)

        if opcode == INSTRUCTION_TYPE["OP_R"]:
            lines.append(
                f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'funct7':^7} | {'rs2':^5} | {'rs1':^5} | {'funct3':^6} | {'rd':^5} | {'opcode':^7} |"
            )
            lines.append(
                f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_funct7:^7} | {bin_rs2:^5} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_rd:^5} | {bin_opcode:^7} |"
            )
        elif opcode in (INSTRUCTION_TYPE["OP_I_IMM"], INSTRUCTION_TYPE["OP_I_LOAD"], INSTRUCTION_TYPE["OP_I_JALR"], INSTRUCTION_TYPE["OP_I_ENV"]):
            lines.append(
                f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[11:0]':^15} | {'rs1':^5} | {'funct3':^6} | {'rd':^5} | {'opcode':^7} |"
            )
            lines.append(
                f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm:^15} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_rd:^5} | {bin_opcode:^7} |"
            )
        elif opcode == INSTRUCTION_TYPE["OP_S"]:
            lines.append(
                f"| {'instruction':^14} | {'inst':^6} | {'type':^8} |{'imm[11:5]':^7}| {'rs2':^5} | {'rs1':^5} | {'funct3':^6} |{'imm[4:0]':^5}| {'opcode':^7} |"
            )
            lines.append(
                f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm11_5:^7} | {bin_rs2:^5} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_imm4_0:^5} | {bin_opcode:^7} |"
            )
        elif opcode == INSTRUCTION_TYPE["OP_B"]:
            lines.append(
                f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[12|10:5]':^7} | {'rs2':^5} | {'rs1':^5} | {'funct3':^6} | {'imm[4:1|11]':^5} | {'opcode':^7} |"
            )
            lines.append(
                f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm12_10_5:^7} | {bin_rs2:^5} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_imm4_1_11:^5} | {bin_opcode:^7} |"
            )
        elif opcode == INSTRUCTION_TYPE["OP_J"]:
            lines.append(
                f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[20|10:1|11|19:12]':^40} | {'rd':^5} | {'opcode':^7} |"
            )
            lines.append(
                f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm_jal:^40} | {bin_rd:^5} | {bin_opcode:^7} |"
            )
        elif opcode in (INSTRUCTION_TYPE["OP_U_LUI"], INSTRUCTION_TYPE["OP_U_AUIPC"]):
            lines.append(
                f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[31:12]':^40} | {'rd':^5} | {'opcode':^7} |"
            )
            lines.append(
                f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm_31_12:^40} | {bin_rd:^5} | {bin_opcode:^7} |"
            )
        else:
            lines.append(f"  unknown instruction  {inst_hex}")

        lines.append("=" * 90)
        return "\n".join(lines)

    def c_reg(self, bits: int) -> int:
        return (bits & 0x7) + 8

    def build_cj_imm(self, halfword: int) -> int:
        return (
            (((halfword >> 12) & 0x1) << 11)
            | (((halfword >> 11) & 0x1) << 4)
            | (((halfword >> 9) & 0x3) << 8)
            | (((halfword >> 8) & 0x1) << 10)
            | (((halfword >> 7) & 0x1) << 6)
            | (((halfword >> 6) & 0x1) << 7)
            | (((halfword >> 3) & 0x7) << 1)
            | (((halfword >> 2) & 0x1) << 5)
        )

    def build_cb_imm(self, halfword: int) -> int:
        imm = ((halfword >> 12) & 0x1) << 8 \
            | ((halfword >> 10) & 0x3) << 3 \
            | ((halfword >> 5)  & 0x3) << 6 \
            | ((halfword >> 3)  & 0x3) << 1 \
            | ((halfword >> 2)  & 0x1) << 5
        return imm

    def decode_compressed(self, halfword: int) -> dict:
        """Decode a 16-bit RVC instruction into the same dict shape as
        ``decoding``. Each quadrant/funct3 path expands the compressed
        encoding to its 32-bit equivalent (e.g. ``c.lw`` -> ``lw`` with the
        reconstructed rs1/rd/imm). Unknown encodings return name ``"unknown"``."""
        quadrant = halfword & 0x3
        funct3 = (halfword >> 13) & 0x7

        if quadrant == 0b00:
            if funct3 == 0b000:
                rd = self.c_reg((halfword >> 2) & 0x7)
                imm = (((halfword >> 6) & 0x1) << 2) \
                    | (((halfword >> 5) & 0x1) << 3) \
                    | (((halfword >> 11) & 0x3) << 4) \
                    | (((halfword >> 7) & 0xF) << 6)
                if imm == 0:
                    return {"inst_name": "reserved", "inst_type": "C-Type", "opcode": 0}
                return {
                    "inst_name": "addi", "inst_type": "I-Type",
                    "opcode": 0b0010011, "rd": rd, "funct3": 0,
                    "rs1": 2, "imm": imm,
                }
            elif funct3 == 0b010:
                rd = self.c_reg((halfword >> 2) & 0x7)
                rs1 = self.c_reg((halfword >> 7) & 0x7)
                imm = (((halfword >> 6) & 0x1) << 2) \
                    | (((halfword >> 10) & 0x7) << 3) \
                    | (((halfword >> 5) & 0x1) << 6)
                return {
                    "inst_name": "lw", "inst_type": "I-Type",
                    "opcode": 0b0000011, "rd": rd, "funct3": 2,
                    "rs1": rs1, "imm": imm,
                }
            elif funct3 == 0b110:
                rs2 = self.c_reg((halfword >> 2) & 0x7)
                rs1 = self.c_reg((halfword >> 7) & 0x7)
                imm = (((halfword >> 6) & 0x1) << 2) \
                    | (((halfword >> 10) & 0x7) << 3) \
                    | (((halfword >> 5) & 0x1) << 6)
                return {
                    "inst_name": "sw", "inst_type": "S-Type",
                    "opcode": 0b0100011, "funct3": 2,
                    "rs1": rs1, "rs2": rs2,
                    "imm": imm,
                }

        elif quadrant == 0b01:
            if funct3 == 0b000:
                rd = (halfword >> 7) & 0x1F
                raw_imm = ((halfword >> 2) & 0x1F) | (((halfword >> 12) & 0x1) << 5)
                imm = self.sign_extend(raw_imm, 6) & 0xFFF
                if rd == 0:
                    return {"inst_name": "nop", "inst_type": "I-Type",
                            "opcode": 0b0010011, "rd": 0, "funct3": 0,
                            "rs1": 0, "imm": 0}
                return {
                    "inst_name": "addi", "inst_type": "I-Type",
                    "opcode": 0b0010011, "rd": rd, "funct3": 0,
                    "rs1": rd, "imm": imm,
                }

            elif funct3 == 0b001:
                imm = self.sign_extend(self.build_cj_imm(halfword), 12)
                return {
                    "inst_name": "jal", "inst_type": "J-Type",
                    "opcode": 0b1101111, "rd": 1, "imm": imm,
                }

            elif funct3 == 0b010:
                rd = (halfword >> 7) & 0x1F
                raw_imm = ((halfword >> 2) & 0x1F) | (((halfword >> 12) & 0x1) << 5)
                imm = self.sign_extend(raw_imm, 6) & 0xFFF
                return {
                    "inst_name": "addi", "inst_type": "I-Type",
                    "opcode": 0b0010011, "rd": rd, "funct3": 0,
                    "rs1": 0, "imm": imm,
                }

            elif funct3 == 0b011:
                rd = (halfword >> 7) & 0x1F
                if rd == 2:
                    imm = self.sign_extend(
                        (((halfword >> 6) & 0x1) << 4) \
                        | (((halfword >> 2) & 0x1) << 5) \
                        | (((halfword >> 5) & 0x1) << 6) \
                        | (((halfword >> 3) & 0x3) << 7) \
                        | (((halfword >> 12) & 0x1) << 9),
                        10
                    ) & 0xFFF
                    if imm == 0:
                        return {"inst_name": "reserved", "inst_type": "C-Type", "opcode": 0}
                    return {
                        "inst_name": "addi", "inst_type": "I-Type",
                        "opcode": 0b0010011, "rd": 2, "funct3": 0,
                        "rs1": 2, "imm": imm,
                    }
                else:
                    if rd == 0:
                        return {"inst_name": "reserved", "inst_type": "C-Type", "opcode": 0}
                    imm = self.sign_extend(
                        (((halfword >> 2) & 0x1F) | (((halfword >> 12) & 0x1) << 5)),
                        6
                    ) << 12
                    if (halfword >> 2) & 0x1F == 0 and (halfword >> 12) & 0x1 == 0:
                        return {"inst_name": "reserved", "inst_type": "C-Type", "opcode": 0}
                    return {
                        "inst_name": "lui", "inst_type": "U-Type",
                        "opcode": 0b0110111, "rd": rd,
                        "imm_31_12": (imm >> 12) & 0xFFFFF,
                    }

            elif funct3 == 0b100:
                funct2 = (halfword >> 10) & 0x3
                rd_rs1 = self.c_reg((halfword >> 7) & 0x7)

                if funct2 == 0b00:
                    shamt = ((halfword >> 2) & 0x1F) | (((halfword >> 12) & 0x1) << 5)
                    return {
                        "inst_name": "srli", "inst_type": "I-Type",
                        "opcode": 0b0010011, "rd": rd_rs1, "funct3": 5,
                        "rs1": rd_rs1, "imm": shamt,
                    }
                elif funct2 == 0b01:
                    shamt = ((halfword >> 2) & 0x1F) | (((halfword >> 12) & 0x1) << 5)
                    return {
                        "inst_name": "srai", "inst_type": "I-Type",
                        "opcode": 0b0010011, "rd": rd_rs1, "funct3": 5,
                        "rs1": rd_rs1, "imm": shamt,
                    }
                elif funct2 == 0b10:
                    imm = self.sign_extend(
                        (((halfword >> 2) & 0x1F) | (((halfword >> 12) & 0x1) << 5)),
                        6
                    ) & 0xFFF
                    return {
                        "inst_name": "andi", "inst_type": "I-Type",
                        "opcode": 0b0010011, "rd": rd_rs1, "funct3": 7,
                        "rs1": rd_rs1, "imm": imm,
                    }
                elif funct2 == 0b11:
                    funct6 = (halfword >> 10) & 0x3
                    funct2_ca = (halfword >> 5) & 0x3
                    rs2 = self.c_reg((halfword >> 2) & 0x7)

                    if funct6 == 0b11 and funct2_ca == 0b00:
                        return {
                            "inst_name": "sub", "inst_type": "R-Type",
                            "opcode": 0b0110011, "rd": rd_rs1, "funct3": 0,
                            "rs1": rd_rs1, "rs2": rs2, "funct7": 0x20,
                        }
                    elif funct6 == 0b11 and funct2_ca == 0b01:
                        return {
                            "inst_name": "xor", "inst_type": "R-Type",
                            "opcode": 0b0110011, "rd": rd_rs1, "funct3": 4,
                            "rs1": rd_rs1, "rs2": rs2, "funct7": 0,
                        }
                    elif funct6 == 0b11 and funct2_ca == 0b10:
                        return {
                            "inst_name": "or", "inst_type": "R-Type",
                            "opcode": 0b0110011, "rd": rd_rs1, "funct3": 6,
                            "rs1": rd_rs1, "rs2": rs2, "funct7": 0,
                        }
                    elif funct6 == 0b11 and funct2_ca == 0b11:
                        return {
                            "inst_name": "and", "inst_type": "R-Type",
                            "opcode": 0b0110011, "rd": rd_rs1, "funct3": 7,
                            "rs1": rd_rs1, "rs2": rs2, "funct7": 0,
                        }

            elif funct3 == 0b101:
                imm = self.sign_extend(self.build_cj_imm(halfword), 12)
                return {
                    "inst_name": "jal", "inst_type": "J-Type",
                    "opcode": 0b1101111, "rd": 0, "imm": imm,
                }

            elif funct3 == 0b110:
                rs1 = self.c_reg((halfword >> 7) & 0x7)
                imm = self.sign_extend(self.build_cb_imm(halfword), 9)
                return {
                    "inst_name": "beq", "inst_type": "B-Type",
                    "opcode": 0b1100011, "funct3": 0,
                    "rs1": rs1, "rs2": 0, "imm": imm,
                }

            elif funct3 == 0b111:
                rs1 = self.c_reg((halfword >> 7) & 0x7)
                imm = self.sign_extend(self.build_cb_imm(halfword), 9)
                return {
                    "inst_name": "bne", "inst_type": "B-Type",
                    "opcode": 0b1100011, "funct3": 1,
                    "rs1": rs1, "rs2": 0, "imm": imm,
                }

        elif quadrant == 0b10:
            if funct3 == 0b000:
                rd = (halfword >> 7) & 0x1F
                shamt = ((halfword >> 2) & 0x1F) | (((halfword >> 12) & 0x1) << 5)
                return {
                    "inst_name": "slli", "inst_type": "I-Type",
                    "opcode": 0b0010011, "rd": rd, "funct3": 1,
                    "rs1": rd, "imm": shamt,
                }

            elif funct3 == 0b010:
                rd = (halfword >> 7) & 0x1F
                if rd == 0:
                    return {"inst_name": "reserved", "inst_type": "C-Type", "opcode": 0}
                imm = (((halfword >> 4) & 0x7) << 2) \
                    | (((halfword >> 12) & 0x1) << 5) \
                    | (((halfword >> 2) & 0x3) << 6)
                return {
                    "inst_name": "lw", "inst_type": "I-Type",
                    "opcode": 0b0000011, "rd": rd, "funct3": 2,
                    "rs1": 2, "imm": imm,
                }

            elif funct3 == 0b100:
                bit12 = (halfword >> 12) & 0x1
                rs2 = (halfword >> 2) & 0x1F
                rd = (halfword >> 7) & 0x1F

                if bit12 == 0:
                    if rs2 == 0:
                        if rd == 0:
                            return {"inst_name": "reserved", "inst_type": "C-Type", "opcode": 0}
                        return {
                            "inst_name": "jalr", "inst_type": "I-Type",
                            "opcode": 0b1100111, "rd": 0, "funct3": 0,
                            "rs1": rd, "imm": 0,
                        }
                    else:
                        return {
                            "inst_name": "add", "inst_type": "R-Type",
                            "opcode": 0b0110011, "rd": rd, "funct3": 0,
                            "rs1": 0, "rs2": rs2, "funct7": 0,
                        }
                else:
                    if rd == 0 and rs2 == 0:
                        return {
                            "inst_name": "ebreak", "inst_type": "I-Type",
                            "opcode": 0b1110011, "rd": 0, "funct3": 0,
                            "rs1": 0, "imm": 1,
                        }
                    elif rs2 == 0:
                        return {
                            "inst_name": "jalr", "inst_type": "I-Type",
                            "opcode": 0b1100111, "rd": 1, "funct3": 0,
                            "rs1": rd, "imm": 0,
                        }
                    else:
                        return {
                            "inst_name": "add", "inst_type": "R-Type",
                            "opcode": 0b0110011, "rd": rd, "funct3": 0,
                            "rs1": rd, "rs2": rs2, "funct7": 0,
                        }

            elif funct3 == 0b110:
                rs2 = (halfword >> 2) & 0x1F
                imm = (((halfword >> 9) & 0xF) << 2) \
                    | (((halfword >> 7) & 0x3) << 6)
                return {
                    "inst_name": "sw", "inst_type": "S-Type",
                    "opcode": 0b0100011, "funct3": 2,
                    "rs1": 2, "rs2": rs2,
                    "imm": imm,
                }

        return {"inst_name": "unknown", "inst_type": "C-Type", "opcode": 0}

    def format_compressed(self, halfword: int) -> str:
        decoded = self.decode_compressed(halfword)
        return (
            f"0x{halfword:04x}  "
            f"{decoded['inst_name']:<8} "
            f"type={decoded['inst_type']}"
        )

    def decoding(self, inst: int) -> dict:
        """Decode a 32-bit instruction into a flat field dict.

        The returned dict always has ``inst_name`` and ``inst_type``; the rest
        depends on the type (rd/rs1/rs2/funct3/funct7 for R, +imm for I/S/B/J,
        imm_31_12 for U, csr_addr/uimm for CSR-immediate forms). CSR/mret are
        re-tagged ``inst_type="CSR-Type"``. Unknown encodings return name
        ``"unknown"`` so the simulator can raise an illegal-instruction trap."""
        inst_hex = f"0x{inst:08x}"
        f = self.parse_fields(inst)
        opcode, rd, funct3 = f["opcode"], f["rd"], f["funct3"]
        rs1, rs2, funct7 = f["rs1"], f["rs2"], f["funct7"]
        imm_i = f["imm_i"]
        imm4_0, imm11_5 = f["imm4_0"], f["imm11_5"]
        imm4_1_11, imm12_10_5 = f["imm4_1_11"], f["imm12_10_5"]

        inst_name = self.get_inst_name(opcode, funct3, funct7, imm_i)
        inst_type = self.get_inst_type(opcode)

        if inst_name in FUNCT3_CSR.values() or inst_name == "mret":
            inst_type = "CSR-Type"

        if opcode == INSTRUCTION_TYPE["OP_R"]:
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_rd = f"{rd:05b}"
                bin_funct3 = f"{funct3:03b}"
                bin_rs1 = f"{rs1:05b}"
                bin_rs2 = f"{rs2:05b}"
                bin_funct7 = f"{funct7:07b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'funct7':^7} | {'rs2':^5} | {'rs1':^5} | {'funct3':^6} | {'rd':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_funct7:^7} | {bin_rs2:^5} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_rd:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "rd": rd,
                "funct3": funct3,
                "rs1": rs1,
                "rs2": rs2,
                "funct7": funct7,
            }

        elif opcode == INSTRUCTION_TYPE["OP_I_IMM"]:
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_rd = f"{rd:05b}"
                bin_funct3 = f"{funct3:03b}"
                bin_rs1 = f"{rs1:05b}"
                bin_imm = f"{imm_i:012b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[11:0]':^15} | {'rs1':^5} | {'funct3':^6} | {'rd':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm:^15} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_rd:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "rd": rd,
                "funct3": funct3,
                "rs1": rs1,
                "imm": imm_i,
                "csr_addr": imm_i,
                "uimm": rs1,
            }

        elif opcode == INSTRUCTION_TYPE["OP_I_LOAD"]:
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_rd = f"{rd:05b}"
                bin_funct3 = f"{funct3:03b}"
                bin_rs1 = f"{rs1:05b}"
                bin_imm = f"{imm_i:012b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[11:0]':^15} | {'rs1':^5} | {'funct3':^6} | {'rd':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm:^15} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_rd:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "rd": rd,
                "funct3": funct3,
                "rs1": rs1,
                "imm": imm_i,
            }

        elif opcode == INSTRUCTION_TYPE["OP_I_JALR"]:
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_rd = f"{rd:05b}"
                bin_funct3 = f"{funct3:03b}"
                bin_rs1 = f"{rs1:05b}"
                bin_imm = f"{imm_i:012b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[11:0]':^15} | {'rs1':^5} | {'funct3':^6} | {'rd':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm:^15} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_rd:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "rd": rd,
                "funct3": funct3,
                "rs1": rs1,
                "imm": imm_i,
            }

        elif opcode == INSTRUCTION_TYPE["OP_I_ENV"]:
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_rd = f"{rd:05b}"
                bin_funct3 = f"{funct3:03b}"
                bin_rs1 = f"{rs1:05b}"
                bin_imm = f"{imm_i:012b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[11:0]':^15} | {'rs1':^5} | {'funct3':^6} | {'rd':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm:^15} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_rd:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "rd": rd,
                "funct3": funct3,
                "rs1": rs1,
                "imm": imm_i,
                "csr_addr": imm_i,
                "uimm": rs1,
            }

        elif opcode == INSTRUCTION_TYPE["OP_S"]:
            imm = self.build_s_imm(f)
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_funct3 = f"{funct3:03b}"
                bin_rs1 = f"{rs1:05b}"
                bin_rs2 = f"{rs2:05b}"
                bin_imm4_0 = f"{imm4_0:05b}"
                bin_imm11_5 = f"{imm11_5:07b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} |{'imm[11:5]':^7}| {'rs2':^5} | {'rs1':^5} | {'funct3':^6} |{'imm[4:0]':^5}| {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm11_5:^7} | {bin_rs2:^5} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_imm4_0:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "funct3": funct3,
                "rs1": rs1,
                "rs2": rs2,
                "imm": imm,
            }

        elif opcode == INSTRUCTION_TYPE["OP_B"]:
            imm = self.build_b_imm(f)
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_funct3 = f"{funct3:03b}"
                bin_rs1 = f"{rs1:05b}"
                bin_rs2 = f"{rs2:05b}"
                bin_imm4_1_11 = f"{imm4_1_11:05b}"
                bin_imm12_10_5 = f"{imm12_10_5:07b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[12|10:5]':^7} | {'rs2':^5} | {'rs1':^5} | {'funct3':^6} | {'imm[4:1|11]':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm12_10_5:^7} | {bin_rs2:^5} | {bin_rs1:^5} | {bin_funct3:^6} | {bin_imm4_1_11:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "funct3": funct3,
                "rs1": rs1,
                "rs2": rs2,
                "imm": imm,
            }

        elif opcode == INSTRUCTION_TYPE["OP_J"]:
            imm = self.build_j_imm(f)
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_rd = f"{rd:05b}"
                bin_imm_jal = f"{imm:020b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[20|10:1|11|19:12]':^40} | {'rd':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm_jal:^40} | {bin_rd:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "rd": rd,
                "imm": imm,
            }

        elif opcode == INSTRUCTION_TYPE["OP_U_LUI"]:
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_rd = f"{rd:05b}"
                bin_imm_31_12 = f"{f['imm_31_12']:020b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[31:12]':^40} | {'rd':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm_31_12:^40} | {bin_rd:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "rd": rd,
                "imm_31_12": f["imm_31_12"],
            }

        elif opcode == INSTRUCTION_TYPE["OP_U_AUIPC"]:
            if self.verbose:
                bin_opcode = f"{opcode:07b}"
                bin_rd = f"{rd:05b}"
                bin_imm_31_12 = f"{f['imm_31_12']:020b}"
                dbg("=" * 90)
                dbg(f"| {'instruction':^14} | {'inst':^6} | {'type':^8} | {'imm[31:12]':^40} | {'rd':^5} | {'opcode':^7} |")
                dbg(f"| {inst_hex:^14} | {inst_name:^6} | {inst_type:^8} | {bin_imm_31_12:^40} | {bin_rd:^5} | {bin_opcode:^7} |")
                dbg("=" * 90)
            return {
                "inst_name": inst_name,
                "inst_type": inst_type,
                "opcode": opcode,
                "rd": rd,
                "imm_31_12": f["imm_31_12"],
            }

        return {"inst_name": "unknown", "inst_type": inst_type, "opcode": opcode}
