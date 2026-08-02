"""Architectural register file, program counter, and cycle counter."""

from .constants import WORD_MASK, ABI_NAME

REG_ALIAS = {
    "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
    "t0": 5, "t1": 6, "t2": 7,
    "s0": 8, "fp": 8, "s1": 9,
    "a0": 10, "a1": 11, "a2": 12, "a3": 13,
    "a4": 14, "a5": 15, "a6": 16, "a7": 17,
    "s2": 18, "s3": 19, "s4": 20, "s5": 21,
    "s6": 22, "s7": 23, "s8": 24, "s9": 25,
    "s10": 26, "s11": 27,
    "t3": 28, "t4": 29, "t5": 30, "t6": 31,
}

class Processor:
    START_ADDR = 0
    NUM_REGISTERS = 32
    INSTRUCTION_SIZE = 4

    def __init__(self) -> None:
        self.reset()

    def reset(self, pc: int | None = None) -> None:
        if pc is None:
            pc = self.START_ADDR

        self.pc = pc & WORD_MASK
        self.registers = [0] * self.NUM_REGISTERS
        self.cycles = 0
        self.halted = False

    def read_register(self, idx: int) -> int:
        self.check_register_index(idx)
        return self.registers[idx]

    def write_register(self, idx: int, val: int) -> None:
        self.check_register_index(idx)
        if idx == 0:
            return
        self.registers[idx] = val & WORD_MASK

    def check_register_index(self, idx: int) -> None:
        if not 0 <= idx < self.NUM_REGISTERS:
            raise IndexError(f"register must be in range (x0 - x31) -> {idx}")

    def set_pc(self, val: int) -> None:
        self.pc = val & WORD_MASK

    def increment_pc(self, size: int = 4) -> None:
        self.set_pc(self.pc + size)

    def read_pc(self) -> int:
        return self.pc

    def cycle_count(self) -> None:
        if not self.halted:
            self.cycles += 1

    def halt(self) -> None:
        self.halted = True

    def __getattr__(self, name: str):
        if name in REG_ALIAS:
            return self.registers[REG_ALIAS[name]]
        raise AttributeError(f"Processor has no attribute '{name}'")

    def description(self) -> str:
        lines = []
        lines.append(f"PC:     0x{self.pc:08x}")
        lines.append(f"Halted: {self.halted}")
        lines.append(f"Cycle:  {self.cycles}")
        reg_lines = []
        for i in range(self.NUM_REGISTERS):
            row = f"x{i:<9} | {ABI_NAME[i]:^4} | 0x{self.registers[i]:08x} |"
            reg_lines.append(f"{row}")
        lines.append(f"| {'Register':^8} | {'ABI':^4} | {'Value':^10} |")
        lines.append("-" * 40)
        lines.extend(reg_lines)
        return "\n".join(lines)
