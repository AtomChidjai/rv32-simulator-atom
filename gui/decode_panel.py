"""Structured Decode-panel presentation for native RV32IMC encodings."""

from html import escape

from rv32i.constants import ABI_NAME, CSR_ADDR


_CSR_NAMES = {address: name for name, address in CSR_ADDR.items()}
_LOAD_WIDTH = {"lb": 8, "lh": 16, "lw": 32, "lbu": 8, "lhu": 16}
_STORE_WIDTH = {"sb": 8, "sh": 16, "sw": 32}
_BRANCH_OP = {
    "beq": "==",
    "bne": "!=",
    "blt": "< signed",
    "bge": ">= signed",
    "bltu": "< unsigned",
    "bgeu": ">= unsigned",
}
_BINARY_OP = {
    "add": "+",
    "sub": "-",
    "xor": "^",
    "or": "|",
    "and": "&",
    "sll": "<<",
    "srl": ">> logical",
    "sra": ">> arithmetic",
    "slt": "< signed",
    "sltu": "< unsigned",
}
_IMMEDIATE_OP = {
    "addi": "+",
    "xori": "^",
    "ori": "|",
    "andi": "&",
    "slli": "<<",
    "srli": ">> logical",
    "srai": ">> arithmetic",
    "slti": "< signed",
    "sltiu": "< unsigned",
}


def signed(value: int, bits: int) -> int:
    value &= (1 << bits) - 1
    sign = 1 << (bits - 1)
    return value - (1 << bits) if value & sign else value


def abi(register: int) -> str:
    return ABI_NAME.get(register, f"x{register}")


def reg(register: int) -> str:
    return f"{abi(register)} (x{register})"


def raw_field(
    instruction: int,
    lsb: int,
    bits: int,
    label: str,
    role: str = "control",
) -> dict:
    value = (instruction >> lsb) & ((1 << bits) - 1)
    return {
        "bits": bits,
        "name": f"{value:0{bits}b}",
        "attr": label,
        "type": 1,
        "rect": {"class": f"decode-field decode-field-{role}"},
    }


def register_label(field: str, register: int) -> str:
    return f"{field} x{register}/{abi(register)}"


def standard_fields(instruction: int, decoded: dict) -> list[dict]:
    opcode = instruction & 0x7F
    name = decoded.get("inst_name", "unknown")
    inst_type = decoded.get("inst_type", "unknown")
    invalid = name == "unknown"

    if invalid:
        return [
            raw_field(instruction, 0, 7, "unsupported opcode", "invalid"),
            raw_field(instruction, 7, 25, "unrecognized payload", "unused"),
        ]

    if inst_type == "R-Type":
        return [
            raw_field(instruction, 0, 7, "opcode", "opcode"),
            raw_field(instruction, 7, 5, register_label("rd", decoded["rd"]), "register"),
            raw_field(instruction, 12, 3, "funct3"),
            raw_field(instruction, 15, 5, register_label("rs1", decoded["rs1"]), "register"),
            raw_field(instruction, 20, 5, register_label("rs2", decoded["rs2"]), "register"),
            raw_field(instruction, 25, 7, "funct7"),
        ]

    if inst_type == "S-Type":
        return [
            raw_field(instruction, 0, 7, "opcode", "opcode"),
            raw_field(instruction, 7, 5, "imm[4:0]", "immediate"),
            raw_field(instruction, 12, 3, "funct3"),
            raw_field(instruction, 15, 5, register_label("rs1", decoded["rs1"]), "register"),
            raw_field(instruction, 20, 5, register_label("rs2", decoded["rs2"]), "register"),
            raw_field(instruction, 25, 7, "imm[11:5]", "immediate"),
        ]

    if inst_type == "B-Type":
        return [
            raw_field(instruction, 0, 7, "opcode", "opcode"),
            raw_field(instruction, 7, 1, "imm[11]", "immediate"),
            raw_field(instruction, 8, 4, "imm[4:1]", "immediate"),
            raw_field(instruction, 12, 3, "funct3"),
            raw_field(instruction, 15, 5, register_label("rs1", decoded["rs1"]), "register"),
            raw_field(instruction, 20, 5, register_label("rs2", decoded["rs2"]), "register"),
            raw_field(instruction, 25, 6, "imm[10:5]", "immediate"),
            raw_field(instruction, 31, 1, "imm[12]", "immediate"),
        ]

    if inst_type == "U-Type":
        return [
            raw_field(instruction, 0, 7, "opcode", "opcode"),
            raw_field(instruction, 7, 5, register_label("rd", decoded["rd"]), "register"),
            raw_field(instruction, 12, 20, "imm[31:12]", "immediate"),
        ]

    if inst_type == "J-Type":
        return [
            raw_field(instruction, 0, 7, "opcode", "opcode"),
            raw_field(instruction, 7, 5, register_label("rd", decoded["rd"]), "register"),
            raw_field(instruction, 12, 8, "imm[19:12]", "immediate"),
            raw_field(instruction, 20, 1, "imm[11]", "immediate"),
            raw_field(instruction, 21, 10, "imm[10:1]", "immediate"),
            raw_field(instruction, 31, 1, "imm[20]", "immediate"),
        ]

    if inst_type in ("I-Type", "CSR-Type"):
        source_label = "rs1"
        if name.startswith("csrr") and name.endswith("i"):
            source_label = "uimm"
        elif name.startswith("csr"):
            source_label = "rs1"
        fields = [
            raw_field(instruction, 0, 7, "opcode", "opcode"),
            raw_field(instruction, 7, 5, register_label("rd", decoded.get("rd", 0)), "register"),
            raw_field(instruction, 12, 3, "funct3"),
        ]
        if source_label == "uimm":
            fields.append(raw_field(instruction, 15, 5, "uimm", "immediate"))
        else:
            fields.append(
                raw_field(
                    instruction,
                    15,
                    5,
                    register_label("rs1", decoded.get("rs1", 0)),
                    "register",
                )
            )
        if name.startswith("csr"):
            tail_label = "csr[11:0]"
        elif name in ("ecall", "ebreak", "mret"):
            tail_label = "system[11:0]"
        else:
            tail_label = "imm[11:0]"
        fields.append(raw_field(instruction, 20, 12, tail_label, "immediate"))
        return fields

    return [
        raw_field(instruction, 0, 7, f"opcode 0b{opcode:07b}", "invalid"),
        raw_field(instruction, 7, 25, "unrecognized payload", "unused"),
    ]


def compressed_name(instruction: int, decoded: dict) -> str:
    quadrant = instruction & 0x3
    funct3 = (instruction >> 13) & 0x7
    name = decoded.get("inst_name", "unknown")
    if name in ("unknown", "reserved"):
        return f"c.{name}"
    if quadrant == 0:
        return {0: "c.addi4spn", 2: "c.lw", 6: "c.sw"}.get(funct3, "c.unknown")
    if quadrant == 1:
        if funct3 == 0:
            return "c.nop" if decoded.get("rd") == 0 else "c.addi"
        if funct3 == 1:
            return "c.jal"
        if funct3 == 2:
            return "c.li"
        if funct3 == 3:
            return "c.addi16sp" if decoded.get("rd") == 2 else "c.lui"
        if funct3 == 4:
            funct2 = (instruction >> 10) & 0x3
            if funct2 != 3:
                return {0: "c.srli", 1: "c.srai", 2: "c.andi"}[funct2]
            return f"c.{name}"
        return {5: "c.j", 6: "c.beqz", 7: "c.bnez"}.get(funct3, "c.unknown")
    if quadrant == 2:
        if funct3 == 0:
            return "c.slli"
        if funct3 == 2:
            return "c.lwsp"
        if funct3 == 6:
            return "c.swsp"
        if funct3 == 4:
            bit12 = (instruction >> 12) & 1
            rs2 = (instruction >> 2) & 0x1F
            rd = (instruction >> 7) & 0x1F
            if bit12 == 0:
                return "c.jr" if rs2 == 0 else "c.mv"
            if rd == 0 and rs2 == 0:
                return "c.ebreak"
            return "c.jalr" if rs2 == 0 else "c.add"
    return "c.unknown"


def compressed_fields(instruction: int, decoded: dict) -> list[dict]:
    quadrant = instruction & 0x3
    funct3 = (instruction >> 13) & 0x7
    name = decoded.get("inst_name", "unknown")
    q = raw_field(instruction, 0, 2, "quadrant", "opcode")
    f3 = raw_field(instruction, 13, 3, "funct3")

    if name in ("unknown", "reserved"):
        return [q, raw_field(instruction, 2, 11, "unsupported payload", "invalid"), f3]

    if quadrant == 0 and funct3 == 0:
        return [
            q,
            raw_field(instruction, 2, 3, register_label("rd'", decoded["rd"]), "register"),
            raw_field(instruction, 5, 1, "nzuimm[3]", "immediate"),
            raw_field(instruction, 6, 1, "nzuimm[2]", "immediate"),
            raw_field(instruction, 7, 4, "nzuimm[9:6]", "immediate"),
            raw_field(instruction, 11, 2, "nzuimm[5:4]", "immediate"),
            f3,
        ]
    if quadrant == 0 and funct3 in (2, 6):
        value = decoded["rd"] if funct3 == 2 else decoded["rs2"]
        field = "rd'" if funct3 == 2 else "rs2'"
        return [
            q,
            raw_field(instruction, 2, 3, register_label(field, value), "register"),
            raw_field(instruction, 5, 2, "uimm[6|2]", "immediate"),
            raw_field(instruction, 7, 3, register_label("rs1'", decoded["rs1"]), "register"),
            raw_field(instruction, 10, 3, "uimm[5:3]", "immediate"),
            f3,
        ]

    if quadrant == 1 and funct3 in (0, 2):
        register = decoded.get("rd", 0)
        register_field = "rd/rs1" if funct3 == 0 else "rd"
        return [
            q,
            raw_field(instruction, 2, 5, "imm[4:0]", "immediate"),
            raw_field(instruction, 7, 5, register_label(register_field, register), "register"),
            raw_field(instruction, 12, 1, "imm[5]", "immediate"),
            f3,
        ]
    if quadrant == 1 and funct3 == 3 and decoded.get("rd") == 2:
        return [
            q,
            raw_field(instruction, 2, 1, "nzimm[5]", "immediate"),
            raw_field(instruction, 3, 2, "nzimm[8:7]", "immediate"),
            raw_field(instruction, 5, 1, "nzimm[6]", "immediate"),
            raw_field(instruction, 6, 1, "nzimm[4]", "immediate"),
            raw_field(instruction, 7, 5, register_label("rd/rs1", 2), "register"),
            raw_field(instruction, 12, 1, "nzimm[9]", "immediate"),
            f3,
        ]
    if quadrant == 1 and funct3 == 3:
        return [
            q,
            raw_field(instruction, 2, 5, "nzimm[16:12]", "immediate"),
            raw_field(instruction, 7, 5, register_label("rd", decoded["rd"]), "register"),
            raw_field(instruction, 12, 1, "nzimm[17]", "immediate"),
            f3,
        ]
    if quadrant == 1 and funct3 in (1, 5):
        return [
            q,
            raw_field(
                instruction,
                2,
                11,
                "offset[11|4|9:8|10|6|7|3:1|5]",
                "immediate",
            ),
            f3,
        ]
    if quadrant == 1 and funct3 == 4:
        funct2 = (instruction >> 10) & 0x3
        if funct2 == 3:
            return [
                q,
                raw_field(instruction, 2, 3, register_label("rs2'", decoded["rs2"]), "register"),
                raw_field(instruction, 5, 2, "funct2"),
                raw_field(instruction, 7, 3, register_label("rd'/rs1'", decoded["rd"]), "register"),
                raw_field(instruction, 10, 6, "funct6"),
            ]
        immediate = "imm" if funct2 == 2 else "shamt"
        return [
            q,
            raw_field(instruction, 2, 5, f"{immediate}[4:0]", "immediate"),
            raw_field(instruction, 7, 3, register_label("rd'/rs1'", decoded["rd"]), "register"),
            raw_field(instruction, 10, 2, "funct2"),
            raw_field(instruction, 12, 1, f"{immediate}[5]", "immediate"),
            f3,
        ]
    if quadrant == 1 and funct3 in (6, 7):
        return [
            q,
            raw_field(instruction, 2, 5, "offset[7:6|2:1|5]", "immediate"),
            raw_field(instruction, 7, 3, register_label("rs1'", decoded["rs1"]), "register"),
            raw_field(instruction, 10, 2, "offset[4:3]", "immediate"),
            raw_field(instruction, 12, 1, "offset[8]", "immediate"),
            f3,
        ]

    if quadrant == 2 and funct3 == 0:
        return [
            q,
            raw_field(instruction, 2, 5, "shamt[4:0]", "immediate"),
            raw_field(instruction, 7, 5, register_label("rd/rs1", decoded["rd"]), "register"),
            raw_field(instruction, 12, 1, "shamt[5]", "immediate"),
            f3,
        ]
    if quadrant == 2 and funct3 == 2:
        return [
            q,
            raw_field(instruction, 2, 2, "uimm[7:6]", "immediate"),
            raw_field(instruction, 4, 3, "uimm[4:2]", "immediate"),
            raw_field(instruction, 7, 5, register_label("rd", decoded["rd"]), "register"),
            raw_field(instruction, 12, 1, "uimm[5]", "immediate"),
            f3,
        ]
    if quadrant == 2 and funct3 == 4:
        rs2 = (instruction >> 2) & 0x1F
        rd_rs1 = (instruction >> 7) & 0x1F
        return [
            q,
            raw_field(instruction, 2, 5, register_label("rs2", rs2), "register"),
            raw_field(instruction, 7, 5, register_label("rd/rs1", rd_rs1), "register"),
            raw_field(instruction, 12, 1, "funct1"),
            f3,
        ]
    if quadrant == 2 and funct3 == 6:
        return [
            q,
            raw_field(instruction, 2, 5, register_label("rs2", decoded["rs2"]), "register"),
            raw_field(instruction, 7, 2, "uimm[7:6]", "immediate"),
            raw_field(instruction, 9, 4, "uimm[5:2]", "immediate"),
            f3,
        ]
    return [q, raw_field(instruction, 2, 11, "unsupported payload", "invalid"), f3]


def base_assembly(decoded: dict, pc: int, width: int) -> str:
    name = decoded.get("inst_name", "unknown")
    rd = abi(decoded.get("rd", 0))
    rs1 = abi(decoded.get("rs1", 0))
    rs2 = abi(decoded.get("rs2", 0))

    if name in _BINARY_OP or name in {"mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"}:
        return f"{name} {rd}, {rs1}, {rs2}"
    if name in _IMMEDIATE_OP:
        immediate = decoded.get("imm", 0)
        if name in ("slli", "srli", "srai"):
            immediate &= 0x1F
        else:
            immediate = signed(immediate, 12)
        return f"{name} {rd}, {rs1}, {immediate}"
    if name in _LOAD_WIDTH:
        return f"{name} {rd}, {signed(decoded['imm'], 12)}({rs1})"
    if name in _STORE_WIDTH:
        return f"{name} {rs2}, {decoded['imm']}({rs1})"
    if name == "jalr":
        return f"jalr {rd}, {signed(decoded['imm'], 12)}({rs1})"
    if name in _BRANCH_OP:
        return f"{name} {rs1}, {rs2}, {decoded['imm']:+d}"
    if name == "jal":
        return f"jal {rd}, {decoded['imm']:+d}"
    if name in ("lui", "auipc"):
        return f"{name} {rd}, 0x{decoded['imm_31_12']:05x}"
    if name.startswith("csr"):
        csr = _CSR_NAMES.get(decoded["csr_addr"], f"0x{decoded['csr_addr']:03x}")
        source = str(decoded["uimm"]) if name.endswith("i") else rs1
        return f"{name} {rd}, {csr}, {source}"
    if name in ("ecall", "ebreak", "mret", "nop"):
        return name
    return f"{name}  # 0x{pc:08x}, {width * 8}-bit"


def compressed_assembly(c_name: str, decoded: dict) -> str:
    rd = abi(decoded.get("rd", 0))
    rs1 = abi(decoded.get("rs1", 0))
    rs2 = abi(decoded.get("rs2", 0))
    imm = decoded.get("imm", 0)
    signed_imm = signed(imm, 12)

    if c_name == "c.addi4spn":
        return f"c.addi4spn {rd}, sp, {imm}"
    if c_name in ("c.lw", "c.lwsp"):
        return f"{c_name} {rd}, {imm}({rs1})"
    if c_name in ("c.sw", "c.swsp"):
        return f"{c_name} {rs2}, {imm}({rs1})"
    if c_name in ("c.addi", "c.addi16sp", "c.li", "c.andi"):
        return f"{c_name} {rd}, {signed_imm}"
    if c_name == "c.lui":
        return f"c.lui {rd}, 0x{decoded['imm_31_12']:05x}"
    if c_name in ("c.slli", "c.srli", "c.srai"):
        return f"{c_name} {rd}, {imm & 0x1F}"
    if c_name in ("c.sub", "c.xor", "c.or", "c.and", "c.add"):
        return f"{c_name} {rd}, {rs2}"
    if c_name == "c.mv":
        return f"c.mv {rd}, {rs2}"
    if c_name in ("c.j", "c.jal"):
        return f"{c_name} {imm:+d}"
    if c_name in ("c.beqz", "c.bnez"):
        return f"{c_name} {rs1}, {imm:+d}"
    if c_name in ("c.jr", "c.jalr"):
        return f"{c_name} {rs1}"
    return c_name


def instruction_meaning(decoded: dict, pc: int, width: int) -> str:
    name = decoded.get("inst_name", "unknown")
    rd = reg(decoded.get("rd", 0))
    rs1 = reg(decoded.get("rs1", 0))
    rs2 = reg(decoded.get("rs2", 0))

    if name in _BINARY_OP:
        return f"{rd} <- {rs1} {_BINARY_OP[name]} {rs2}"
    if name in {"mul", "mulh", "mulhsu", "mulhu", "div", "divu", "rem", "remu"}:
        return f"{rd} <- {name}({rs1}, {rs2})"
    if name in _IMMEDIATE_OP:
        immediate = decoded.get("imm", 0)
        if name in ("slli", "srli", "srai"):
            immediate &= 0x1F
        else:
            immediate = signed(immediate, 12)
        return f"{rd} <- {rs1} {_IMMEDIATE_OP[name]} {immediate}"
    if name in _LOAD_WIDTH:
        bits = _LOAD_WIDTH[name]
        extend = "zero_extend" if name.endswith("u") else "sign_extend"
        value = f"memory{bits}[{rs1} + {signed(decoded['imm'], 12)}]"
        return f"{rd} <- {value}" if bits == 32 else f"{rd} <- {extend}({value})"
    if name in _STORE_WIDTH:
        bits = _STORE_WIDTH[name]
        return f"memory{bits}[{rs1} + {decoded['imm']}] <- {rs2}"
    if name in _BRANCH_OP:
        target = (pc + decoded["imm"]) & 0xFFFFFFFF
        return f"branch to 0x{target:08x} when {rs1} {_BRANCH_OP[name]} {rs2}"
    if name == "jal":
        target = (pc + decoded["imm"]) & 0xFFFFFFFF
        return f"{rd} <- 0x{(pc + width):08x}; jump to 0x{target:08x}"
    if name == "jalr":
        return f"{rd} <- 0x{(pc + width):08x}; jump to ({rs1} + {signed(decoded['imm'], 12)}) & ~1"
    if name == "lui":
        return f"{rd} <- 0x{(decoded['imm_31_12'] << 12) & 0xFFFFFFFF:08x}"
    if name == "auipc":
        value = (decoded["imm_31_12"] << 12) & 0xFFFFFFFF
        return f"{rd} <- 0x{pc:08x} + 0x{value:08x}"
    if name.startswith("csr"):
        csr = _CSR_NAMES.get(decoded["csr_addr"], f"0x{decoded['csr_addr']:03x}")
        source = str(decoded["uimm"]) if name.endswith("i") else rs1
        operation = {"csrrw": "", "csrrwi": "", "csrrs": " | ", "csrrsi": " | ", "csrrc": " & ~", "csrrci": " & ~"}[name]
        write = source if not operation else f"{csr}{operation}{source}"
        return f"{rd} <- {csr}; {csr} <- {write}"
    if name == "ecall":
        return "raise an environment-call exception"
    if name == "ebreak":
        return "halt at the breakpoint instruction"
    if name == "mret":
        return "return from the current machine-mode trap"
    if name == "nop":
        return "no architectural effect"
    return "Unsupported or reserved instruction encoding"


def instruction_detail(decoded: dict, pc: int, width: int) -> str | None:
    name = decoded.get("inst_name", "unknown")
    if name in _BRANCH_OP or name == "jal":
        immediate = decoded["imm"]
        target = (pc + immediate) & 0xFFFFFFFF
        return f"Reconstructed offset: {immediate:+d}; target: 0x{target:08x}"
    if name.startswith("csr"):
        csr = _CSR_NAMES.get(decoded["csr_addr"], "unknown CSR")
        return f"CSR: {csr} (0x{decoded['csr_addr']:03x})"
    if "imm" in decoded and name not in ("ecall", "ebreak", "mret"):
        immediate = decoded["imm"]
        if decoded.get("inst_type") == "I-Type":
            immediate = signed(immediate, 12)
        return f"Immediate: {immediate} (0x{immediate & 0xFFFFFFFF:08x})"
    if name in ("lui", "auipc"):
        value = (decoded["imm_31_12"] << 12) & 0xFFFFFFFF
        return f"Upper immediate value: 0x{value:08x}"
    return None


def empty_panel(message: str) -> tuple[str, None]:
    return (
        f'<div class="decode-empty">{escape(message)}</div>',
        None,
    )


def build_decode_panel(
    instruction: int | None,
    decoded: dict | None,
    pc: int | None,
    *,
    state: str = "instruction",
) -> tuple[str, dict | None]:
    """Return Decode-panel HTML and an optional WaveDrom register spec."""
    if state in ("trap", "interrupt"):
        event = "trap or interrupt" if state == "trap" else "interrupt"
        return empty_panel(f"No instruction retired. This history entry represents a {event}.")
    if state == "not_started" or instruction is None or decoded is None:
        return empty_panel("Compile and step to inspect an instruction.")

    pc = 0 if pc is None else pc
    width = decoded.get("_inst_size", 4)
    compressed = width == 2
    raw = instruction & (0xFFFF if compressed else 0xFFFFFFFF)
    base_name = decoded.get("inst_name", "unknown")
    display_name = compressed_name(raw, decoded) if compressed else base_name
    family = "C-Type" if compressed else decoded.get("inst_type", "Unknown")
    if not compressed and family == "R-Type" and ((raw >> 25) & 0x7F) == 1:
        family = "R-Type / M"

    assembly = (
        compressed_assembly(display_name, decoded)
        if compressed
        else base_assembly(decoded, pc, width)
    )
    meaning = instruction_meaning(decoded, pc, width)
    detail = instruction_detail(decoded, pc, width)
    fields = (
        compressed_fields(raw, decoded)
        if compressed
        else standard_fields(raw, decoded)
    )
    hex_value = f"0x{raw:04x}" if compressed else f"0x{raw:08x}"
    invalid = base_name in ("unknown", "reserved")
    mnemonic_class = " decode-mnemonic-invalid" if invalid else ""

    parts = [
        '<div class="decode-view">',
        '<div class="panel-context-band decode-context">',
        '<div class="decode-identity">',
        f'<strong class="decode-mnemonic{mnemonic_class}">{escape(display_name.upper())}</strong>',
        f'<span class="decode-family">{escape(family)}</span>',
        f'<span class="decode-pc">PC 0x{pc:08x}</span>',
        f'<span class="decode-raw">{hex_value} / {width * 8}-bit</span>',
        "</div>",
        f'<div class="decode-assembly">{escape(assembly)}</div>',
        f'<div class="decode-effect">{escape(meaning)}</div>',
        "</div>",
    ]
    if compressed and not invalid:
        expanded = base_assembly(decoded, pc, width)
        parts.append(f'<div class="decode-expanded">Expands to: {escape(expanded)}</div>')
    if detail:
        parts.append(f'<div class="decode-detail">{escape(detail)}</div>')
    parts.extend(
        [
            '<div class="decode-encoding-label">Encoding</div>',
            '<div class="decode-bitfield-scroll">',
            '<div id="decode-bitfield" class="decode-bitfield" '
            f'aria-label="{escape(display_name)} encoding">Preparing encoding...</div>',
            "</div>",
            "</div>",
        ]
    )

    source = {
        "reg": fields,
        "config": {
            "bits": width * 8,
            "lanes": 1,
            "hspace": 920 if compressed else 1080,
            "fontsize": 11,
            "fontfamily": "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        },
        "ariaLabel": f"{display_name} {width * 8}-bit instruction encoding",
    }
    return "".join(parts), source
