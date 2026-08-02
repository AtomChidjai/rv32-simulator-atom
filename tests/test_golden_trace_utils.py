import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path


def resolve_executable(name: str) -> str:
    """Prefer the documented local tool directory, then fall back to PATH."""
    local = Path.home() / "opt" / "riscv" / "bin" / name
    return str(local) if local.is_file() else (shutil.which(name) or name)


def executable_available(executable: str) -> bool:
    return Path(executable).is_file() or shutil.which(executable) is not None


RISCV_GCC = resolve_executable("riscv64-unknown-elf-gcc")
RISCV_OBJDUMP = resolve_executable("riscv64-unknown-elf-objdump")
SPIKE = resolve_executable("spike")
SPIKE_ISA = "rv32im"
SPIKE_MEMORY_BASE = 0x80000000
SPIKE_MEMORY_SIZE = 0x100000

SPIKE_CFLAGS = [
    "-march=rv32im",
    "-mabi=ilp32",
    "-nostartfiles",
    "-nostdlib",
    "-ffreestanding",
    "-O0",
]

ABI_NAMES = [
    "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
    "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
    "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
    "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
]


class SpikeRunner:
    def __init__(self):
        self.spike = SPIKE
        self.gcc = RISCV_GCC
        self.isa = SPIKE_ISA

    def compile_for_spike(self, c_file: str, elf_file: str = None) -> str:
        if elf_file is None:
            fd, elf_file = tempfile.mkstemp(suffix=".elf")
            os.close(fd)

        text_addr = SPIKE_MEMORY_BASE + 0x1000
        cflags = SPIKE_CFLAGS + [f"-Wl,-Ttext=0x{text_addr:x}"]
        cmd = [self.gcc] + cflags + ["-o", elf_file, c_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"Spike compilation failed:\n{result.stderr}")
        return elf_file

    def find_ebreak_addr(self, elf_file: str) -> int:
        cmd = [RISCV_OBJDUMP, "-d", elf_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"objdump failed:\n{result.stderr}")

        ebreak_addr = None
        for line in result.stdout.splitlines():
            if "ebreak" in line:
                match = re.match(r"\s*([0-9a-f]+):", line)
                if match:
                    ebreak_addr = int(match.group(1), 16)
        if ebreak_addr is None:
            raise RuntimeError("No ebreak instruction found in ELF")
        return ebreak_addr

    def run_to_ebreak(self, elf_file: str) -> dict[str, int]:
        ebreak_addr = self.find_ebreak_addr(elf_file)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write(f"until pc 0 0x{ebreak_addr:x}\n")
            f.write("reg 0\n")
            f.write("quit\n")
            cmd_file = f.name

        try:
            memory_spec = f"0x{SPIKE_MEMORY_BASE:x}:0x{SPIKE_MEMORY_SIZE:x}"
            cmd = [
                self.spike,
                f"--isa={self.isa}",
                "--disable-dtb",
                f"--pc=0x{SPIKE_MEMORY_BASE + 0x1000:x}",
                f"-m{memory_spec}",
                "-d",
                f"--debug-cmd={cmd_file}",
                elf_file,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode != 0:
                raise RuntimeError(f"Spike execution failed:\n{result.stderr}")
            registers = self.parse_reg_dump(result.stderr)
            missing = [name for name in ABI_NAMES if name not in registers]
            if missing:
                raise RuntimeError(
                    "Spike register dump was incomplete; missing: "
                    + ", ".join(missing)
                )
            return registers
        finally:
            os.unlink(cmd_file)

    def parse_reg_dump(self, text: str) -> dict[str, int]:
        regs = {}
        pattern = r"(\w+):\s+(0x[0-9a-fA-F]+)"
        for match in re.finditer(pattern, text):
            name = match.group(1)
            value = int(match.group(2), 16)
            if name in ABI_NAMES:
                regs[name] = value
        return regs

    def get_golden_state(self, c_file: str) -> dict[str, int]:
        elf_file = self.compile_for_spike(c_file)
        try:
            return self.run_to_ebreak(elf_file)
        finally:
            os.unlink(elf_file)
