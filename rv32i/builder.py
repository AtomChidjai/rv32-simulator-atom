"""C/assembly-to-ELF/binary helpers for the external RISC-V toolchain."""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

RISCV_PREFIX = "riscv64-unknown-elf-"
TOOL_TIMEOUT_SECONDS = 30


class ToolchainError(RuntimeError):
    """A missing, failed, or unresponsive external RISC-V tool."""


def resolve_tool(name: str) -> str:
    executable = f"{RISCV_PREFIX}{name}"
    local = os.path.expanduser(f"~/opt/riscv/bin/{executable}")
    return local if os.path.isfile(local) else (shutil.which(executable) or executable)


RISCV_GCC = resolve_tool("gcc")
RISCV_OBJCOPY = resolve_tool("objcopy")
RISCV_OBJDUMP = resolve_tool("objdump")
_BUILD_DIR = tempfile.TemporaryDirectory(prefix="rv32i-build-")

_DEFAULT_LD = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts", "default.ld")

LINK_MODE_NO_LINKER = "no_linker"
LINK_MODE_LINKER = "linker"
LINK_MODES = [LINK_MODE_NO_LINKER, LINK_MODE_LINKER]

DEFAULT_LINK_MODE = LINK_MODE_NO_LINKER
DEFAULT_LINKER_SCRIPT = _DEFAULT_LD

DEFAULT_CFLAGS = [
    "-march=rv32imc_zicsr",
    "-mabi=ilp32",
    "-nostartfiles",
    "-nostdlib",
    "-ffreestanding",
    "-O0",
    "-Ttext=0x10000",
]
# The fixed text base prevents objcopy from copying ELF headers into the binary.
DEFAULT_ARCH = "rv32imc_zicsr"

ARCH_OPTIONS = [
    {"label": "RV32I  (base + Zicsr)",              "march": "rv32i_zicsr"},
    {"label": "RV32IM (base + mul/div + Zicsr)",    "march": "rv32im_zicsr"},
    {"label": "RV32IC (base + compressed + Zicsr)", "march": "rv32ic_zicsr"},
    {"label": "RV32IMC (base + mul + comp + Zicsr)", "march": "rv32imc_zicsr"},
]


def cflags_for(march: str) -> list[str]:
    """DEFAULT_CFLAGS with the -march= entry swapped to `march`."""
    return [f if not f.startswith("-march=") else f"-march={march}" for f in DEFAULT_CFLAGS]


def apply_link_mode(cflags: list[str], link_mode: str, linker_script: str | None) -> list[str]:
    """Return compiler flags for the requested link mode."""
    if link_mode == LINK_MODE_NO_LINKER:
        return cflags
    if link_mode == LINK_MODE_LINKER:
        script = linker_script if linker_script else DEFAULT_LINKER_SCRIPT
        if not os.path.isfile(script):
            raise FileNotFoundError(f"linker script not found: {script}")
        without_ttext = [f for f in cflags if not f.startswith("-Ttext=")]
        return without_ttext + ["-T", script]
    raise ValueError(f"unknown link_mode: {link_mode!r} (expected one of {LINK_MODES})")


def run_tool(cmd: list[str], action: str) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ToolchainError(
            f"{action} timed out after {TOOL_TIMEOUT_SECONDS} seconds"
        ) from exc
    except FileNotFoundError as exc:
        raise ToolchainError(
            f"RISC-V tool not found: {cmd[0]}. "
            "Install the riscv64-unknown-elf toolchain or place it on PATH."
        ) from exc
    except OSError as exc:
        raise ToolchainError(f"could not start {cmd[0]}: {exc}") from exc

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        raise ToolchainError(f"{action} failed:\n{detail}")
    return result


def compile_c_to_elf(c_file: str, elf_file: str, cflags: list[str] | None = None) -> None:
    """Run GCC on a C or assembly source and produce an ELF."""
    if cflags is None:
        cflags = DEFAULT_CFLAGS

    cmd = [RISCV_GCC] + cflags + ["-o", elf_file, c_file]
    run_tool(cmd, "compilation")


def elf_to_bin(elf_file: str, bin_file: str) -> None:
    """Run objcopy to produce a flat binary from the ELF. Raises on failure."""
    cmd = [RISCV_OBJCOPY, "-O", "binary", elf_file, bin_file]
    run_tool(cmd, "objcopy")


def build(
    c_file: str,
    bin_file: str | None = None,
    march: str | None = None,
    link_mode: str = DEFAULT_LINK_MODE,
    linker_script: str | None = None,
) -> dict:
    """Compile a C or assembly source to ELF plus a flat binary."""
    stem = Path(c_file).stem
    base = os.path.join(_BUILD_DIR.name, f"{stem}-{uuid4().hex}")
    elf_file = f"{base}.elf"

    cflags = cflags_for(march) if march is not None else DEFAULT_CFLAGS
    cflags = apply_link_mode(cflags, link_mode, linker_script)
    compile_c_to_elf(c_file, elf_file, cflags=cflags)

    if bin_file is None:
        bin_file = f"{base}.bin"

    elf_to_bin(elf_file, bin_file)

    return {
        "elf_file": elf_file,
        "bin_file": bin_file,
        "link_mode": link_mode,
        "linker_script": linker_script,
    }


def get_disassembly(elf_file: str) -> str:
    """Return objdump disassembly text (used by the GUI asm view)."""
    cmd = [RISCV_OBJDUMP, "-d", "--no-show-raw-insn", elf_file]
    result = run_tool(cmd, "objdump")
    return result.stdout
