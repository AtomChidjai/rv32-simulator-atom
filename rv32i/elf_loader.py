"""Read RISC-V ELF layout and symbols using GNU binutils."""

import os
import shlex
import shutil
import subprocess

TOOL_TIMEOUT_SECONDS = 30


class ELFLoadError(RuntimeError):
    """A failed ELF metadata command or malformed metadata response."""

def resolve_tool(name: str) -> str:
    prefix = "riscv64-unknown-elf-"
    executable = prefix + name
    local = os.path.expanduser(f"~/opt/riscv/bin/{executable}")
    return local if os.path.isfile(local) else (shutil.which(executable) or executable)

def run(cmd: list[str]) -> str:
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=TOOL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ELFLoadError(
            f"{cmd[0]} timed out after {TOOL_TIMEOUT_SECONDS} seconds"
        ) from exc
    except FileNotFoundError as exc:
        raise ELFLoadError(
            f"RISC-V ELF tool not found: {cmd[0]}. "
            "Install the riscv64-unknown-elf binutils or place them on PATH."
        ) from exc
    except OSError as exc:
        raise ELFLoadError(f"could not start {cmd[0]}: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "no diagnostic output"
        command = " ".join(shlex.quote(c) for c in cmd)
        raise ELFLoadError(f"{command} failed:\n{detail}")
    return result.stdout


def parse_hex(value: str, context: str) -> int:
    try:
        return int(value, 16)
    except ValueError as exc:
        raise ELFLoadError(f"invalid {context}: {value!r}") from exc


def load_elf(elf_path: str) -> dict:
    """Scrape entry point, sections, and global pointer from an ELF file."""
    readelf = resolve_tool("readelf")
    objdump = resolve_tool("objdump")
    nm = resolve_tool("nm")

    # --- entry point ---
    header = run([readelf, "-h", elf_path])
    entry = None
    for line in header.splitlines():
        if "Entry point address:" in line:
            entry = parse_hex(line.split(":")[-1].strip(), "ELF entry point")
            break
    if entry is None:
        raise ELFLoadError("ELF header has no entry point")

    # --- sections via objdump -h ---
    sections = []
    text_addr = None
    load_addrs = []
    sec_out = run([objdump, "-h", elf_path])
    lines = [l for l in sec_out.splitlines() if l.strip()]

    i = 0
    while i < len(lines):
        # look for the start of the section table
        if lines[i].startswith("Sections:"):
            i += 2
            continue

        parts = lines[i].split()
        if i + 1 >= len(lines) or not parts[0].isdigit():
            i += 1
            continue
        if len(parts) < 5:
            raise ELFLoadError(f"malformed ELF section row: {lines[i]!r}")

        # line i:   0 .text  0000005c  00010000  00010000  00001000  2**2
        # line i+1:          CONTENTS, ALLOC, LOAD, READONLY, CODE
        name = parts[1]
        addr = parse_hex(parts[3], f"address for section {name}")
        section_load_addr = parse_hex(parts[4], f"load address for section {name}")
        flags_line = lines[i + 1].strip()
        flags = flags_line.replace(",", " ").split()

        if "ALLOC" not in flags:
            i += 2
            continue

        sections.append({
            "name": name,
            "addr": addr,
            "load_addr": section_load_addr,
            "flags": flags,
        })
        if "CONTENTS" in flags and "LOAD" in flags:
            load_addrs.append(section_load_addr)
        if name == ".text":
            text_addr = addr
        i += 2

    if text_addr is None:
        raise ELFLoadError("no .text section found in ELF")
    if not load_addrs:
        raise ELFLoadError("no loadable contents found in ELF")

    # --- global pointer ---
    global_pointer = None
    stack_top = 0x7FFFFFF0
    sym_out = run([nm, elf_path])
    for line in sym_out.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        symbol = parts[-1]
        if symbol == "__global_pointer$":
            global_pointer = parse_hex(parts[0], "__global_pointer$ value")
        elif symbol == "__stack_top":
            stack_top = parse_hex(parts[0], "__stack_top value")

    return {
        "entry_point": entry,
        "text_addr": text_addr,
        "load_addr": min(load_addrs),
        "sections": sections,
        "global_pointer": global_pointer,
        "stack_top": stack_top,
    }


def print_section_map(info: dict, file=None) -> None:
    items = info.get("sections", [])
    if not items:
        return
    header = f"  {'Name':<14} {'Address':<12}"
    print("=== Section Map ===", file=file)
    print(header, file=file)
    print(f"  {'-' * 14} {'-' * 12}", file=file)
    for it in items:
        print(f"  {it['name']:<14} 0x{it['addr']:08x}", file=file)
    print(file=file)
