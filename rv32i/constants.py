"""Instruction, register, CSR, and MMIO constants for RV32IMC + Zicsr."""

WORD_SIZE = 32
WORD_BYTES = WORD_SIZE // 8
WORD_MASK = (1 << WORD_SIZE) - 1  # 0xFFFFFFFF

MMIO_CONSOLE_OUT = 0x10000000
MMIO_CONSOLE_IN  = 0x10000004

INSTRUCTION_TYPE = {
    "OP_R"      : 0b0110011,
    "OP_I_IMM"  : 0b0010011,
    "OP_I_LOAD" : 0b0000011,
    "OP_I_JALR" : 0b1100111,
    "OP_I_ENV"  : 0b1110011,
    "OP_S"      : 0b0100011,
    "OP_B"      : 0b1100011,
    "OP_J"      : 0b1101111,
    "OP_U_LUI"  : 0b0110111,
    "OP_U_AUIPC": 0b0010111,
}

RTYPE_FUNCT3_FUNCT7 = {
    "add"   : [0b000, 0b0000000],
    "sub"   : [0b000, 0b0100000],
    "xor"   : [0b100, 0b0000000],
    "or"    : [0b110, 0b0000000],
    "and"   : [0b111, 0b0000000],
    "sll"   : [0b001, 0b0000000],
    "srl"   : [0b101, 0b0000000],
    "sra"   : [0b101, 0b0100000],
    "slt"   : [0b010, 0b0000000],
    "sltu"  : [0b011, 0b0000000],

    # Multiply Extension
    "mul"   : [0b000, 0b0000001],
    "mulh"  : [0b001, 0b0000001],
    "mulhsu": [0b010, 0b0000001],
    "mulhu" : [0b011, 0b0000001],
    "div"   : [0b100, 0b0000001],
    "divu"  : [0b101, 0b0000001],
    "rem"   : [0b110, 0b0000001],
    "remu"  : [0b111, 0b0000001],
}

ITYPE_FUNCT3_IMM = {
    "addi"  : [0b000, 0b0000000],
    "xori"  : [0b100, 0b0000000],
    "ori"   : [0b110, 0b0000000],
    "andi"  : [0b111, 0b0000000],
    "slli"  : [0b001, 0b0000000],
    "srli"  : [0b101, 0b0000000],
    "srai"  : [0b101, 0b0100000],
    "slti"  : [0b010, 0b0000000],
    "sltiu" : [0b011, 0b0000000],
}

FUNCT3_LOAD = {
    0b000: "lb",
    0b001: "lh",
    0b010: "lw",
    0b100: "lbu",
    0b101: "lhu",
}

FUNCT3_JALR = {
    0b000: "jalr",
}

FUNCT3_STYPE = {
    0b000: "sb",
    0b001: "sh",
    0b010: "sw",
}

FUNCT3_BTYPE = {
    0b000: "beq",
    0b001: "bne",
    0b100: "blt",
    0b101: "bge",
    0b110: "bltu",
    0b111: "bgeu",
}

ABI_NAME = {
    0   : "zero",   # Hard-wired zero
    1   : "ra",     # Return address
    2   : "sp",     # Stack pointer
    3   : "gp",     # Global pointer
    4   : "tp",     # Thread pointer
    5   : "t0",     # Temporary 0
    6   : "t1",     # Temporary 1
    7   : "t2",     # Temporary 2
    8   : "s0",     # Saved register 0 / Frame pointer (fp)
    9   : "s1",     # Saved register 1
    10  : "a0",     # Function argument 0 / Return value 0
    11  : "a1",     # Function argument 1 / Return value 1
    12  : "a2",     # Function argument 2
    13  : "a3",     # Function argument 3
    14  : "a4",     # Function argument 4
    15  : "a5",     # Function argument 5
    16  : "a6",     # Function argument 6
    17  : "a7",     # Function argument 7
    18  : "s2",     # Saved register 2
    19  : "s3",     # Saved register 3
    20  : "s4",     # Saved register 4
    21  : "s5",     # Saved register 5
    22  : "s6",     # Saved register 6
    23  : "s7",     # Saved register 7
    24  : "s8",     # Saved register 8
    25  : "s9",     # Saved register 9
    26  : "s10",    # Saved register 10
    27  : "s11",    # Saved register 11
    28  : "t3",     # Temporary 3
    29  : "t4",     # Temporary 4
    30  : "t5",     # Temporary 5
    31  : "t6",     # Temporary 6
}

CSR_ADDR = {
    "mstatus"   : 0x300,
    "misa"      : 0x301,
    "mie"       : 0x304,
    "mtvec"     : 0x305,
    "mscratch"  : 0x340,
    "mepc"      : 0x341,
    "mcause"    : 0x342,
    "mtval"     : 0x343,
    "mip"       : 0x344,
    "mcycle"    : 0xB00,
    "minstret"  : 0xB02,
}

INTERRUPT_PRIORITY = [11, 3, 7]  # MEI > MSI > MTI (highest first)

FUNCT3_CSR = {
    0b001: "csrrw",
    0b010: "csrrs",
    0b011: "csrrc",
    0b101: "csrrwi",
    0b110: "csrrsi",
    0b111: "csrrci",
}

# SYSTEM opcode funct3=000 sub-types (imm[31:20])
ENV_IMM = {
    "ecall" : 0x000,
    "ebreak": 0x001,
    "mret"  : 0x302,
}
