"""HTML renderers for simulator state and timing panels."""

from html import escape
import re

from rv32i.constants import ABI_NAME, CSR_ADDR
from rv32i.cache import WORD_BYTES
from gui.theme import (
    C_BG, C_FG, C_FG_DIM, C_ACCENT, C_GREEN, C_RED,
    C_YELLOW, C_CYAN, C_BORDER, C_CURRENT,
    C_ACCENT_SOFT, C_GREEN_SOFT, C_RED_SOFT, C_YELLOW_SOFT,
)

# Spacing scale shared by all table renderers (tuned for an airy, readable grid).
_CELL_XS = "4px 6px"
_CELL_SM = "5px 8px"


# ── Disassembly parsing ────────────────────────────────────────────────
def parse_disassembly(text: str) -> tuple[list[str], dict[int, int]]:
    """Parse `objdump`-style disassembly into (lines, pc_to_line)."""
    lines = []
    pc_to_line = {}
    for line in text.splitlines():
        section_match = re.match(r"\s*Disassembly of section\s+(.+):\s*$", line)
        instruction_match = re.match(r"\s*([0-9a-fA-F]+):\s+(.+)", line)
        if section_match:
            continue
        elif instruction_match:
            addr = int(instruction_match.group(1), 16)
            pc_to_line[addr] = len(lines)
            lines.append(
                f"{instruction_match.group(1)}: {instruction_match.group(2)}"
            )
        elif line.strip() and "file format" not in line:
            lines.append(line.strip())
    return lines, pc_to_line


# ── Register table ─────────────────────────────────────────────────────
def build_register_table_html(
    registers: list[int],
    changed_registers: set[int] | None = None,
) -> str:
    changed = changed_registers or set()
    rows = []
    for i in range(32):
        abi = ABI_NAME[i]
        val = registers[i]
        is_changed = i in changed
        bg = f"background:{C_CURRENT};" if is_changed else ""
        color = C_GREEN if is_changed else (C_FG if val != 0 else C_FG_DIM)
        marker = "▸" if is_changed else ""
        changed_label = "changed" if is_changed else "unchanged"
        rows.append(
            f'<tr data-changed="{str(is_changed).lower()}" '
            f'aria-label="x{i} {abi}, {changed_label}" style="{bg}">'
            f'<td class="state-marker-cell" aria-label="{changed_label}" '
            f'style="color:{C_GREEN};padding:{_CELL_SM};text-align:center">'
            f'<span aria-hidden="true">{marker}</span></td>'
            f'<td style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:right;white-space:nowrap">{i}</td>'
            f'<td style="color:{C_ACCENT};padding:{_CELL_SM};white-space:nowrap">{abi}</td>'
            f'<td style="color:{color};padding:{_CELL_SM};font-family:monospace;width:100%">0x{val:08x}</td>'
            f'</tr>'
        )
    return (
        f'<table class="register-table" style="width:100%;border-collapse:collapse;font-size:12px;line-height:1.5">'
        f'<thead><tr style="background:{C_BG};border-bottom:1px solid {C_BORDER}">'
        f'<th class="state-marker-cell" aria-label="Changed in latest clock" '
        f'style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:center;font-weight:500">▸</th>'
        f'<th style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:right;font-weight:500;white-space:nowrap">#</th>'
        f'<th style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:left;font-weight:500;white-space:nowrap">ABI</th>'
        f'<th style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:left;font-weight:500;width:100%">Value</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


# ── CSR table ──────────────────────────────────────────────────────────
def build_csr_table_html(
    csr_dict: dict[int, int],
    changed_csrs: set[int] | None = None,
) -> str:
    names = {v: k for k, v in CSR_ADDR.items()}
    changed = changed_csrs or set()
    rows = []
    for addr in sorted(csr_dict.keys()):
        val = csr_dict[addr]
        name = names.get(addr, f"0x{addr:03x}")
        is_changed = addr in changed
        bg = f"background:{C_CURRENT};" if is_changed else ""
        color = C_GREEN if is_changed else (C_FG if val != 0 else C_FG_DIM)
        marker = "▸" if is_changed else ""
        changed_label = "changed" if is_changed else "unchanged"
        rows.append(
            f'<tr data-changed="{str(is_changed).lower()}" '
            f'aria-label="{escape(name)}, {changed_label}" style="{bg}">'
            f'<td class="state-marker-cell" aria-label="{changed_label}" '
            f'style="color:{C_GREEN};padding:{_CELL_SM};text-align:center">'
            f'<span aria-hidden="true">{marker}</span></td>'
            f'<td style="color:{C_ACCENT};padding:{_CELL_SM};white-space:nowrap">{name}</td>'
            f'<td style="color:{C_FG_DIM};padding:{_CELL_SM};white-space:nowrap">0x{addr:03x}</td>'
            f'<td style="color:{color};padding:{_CELL_SM};font-family:monospace;width:100%">0x{val:08x}</td>'
            f'</tr>'
        )
    return (
        f'<table class="register-table csr-table" style="width:100%;border-collapse:collapse;font-size:12px;line-height:1.5">'
        f'<thead><tr style="background:{C_BG};border-bottom:1px solid {C_BORDER}">'
        f'<th class="state-marker-cell" aria-label="Changed in latest clock" '
        f'style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:center;font-weight:500">▸</th>'
        f'<th style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:left;font-weight:500;white-space:nowrap">Name</th>'
        f'<th style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:left;font-weight:500;white-space:nowrap">Addr</th>'
        f'<th style="color:{C_FG_DIM};padding:{_CELL_SM};text-align:left;font-weight:500;width:100%">Value</th>'
        f'</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )


def build_trap_log_html(entries: list[dict]) -> str:
    """Render the latest trap as primary context and keep older entries flat."""
    if not entries:
        return f'<div class="trap-empty" style="color:{C_FG_DIM}">(no traps)</div>'

    def render_entry(entry: dict, *, latest: bool) -> str:
        kind = str(entry.get("kind", "TRAP"))
        kind_color = C_YELLOW if kind == "INT" else C_RED
        cause_name = escape(str(entry.get("cause_name", "Unknown trap")))
        cycle = int(entry.get("cycle", 0))
        mepc = int(entry.get("mepc", 0))
        mtvec = int(entry.get("mtvec", 0))
        mtval = int(entry.get("mtval", 0))
        priority = int(entry.get("priority", -1))
        priority_html = (
            f'<span>Priority {priority + 1}</span>'
            if kind == "INT" and priority >= 0
            else ""
        )
        halted_html = (
            f'<strong class="trap-halted" style="color:{C_RED}">HALTED</strong>'
            if entry.get("halted")
            else ""
        )
        classes = "panel-context-band trap-latest" if latest else "trap-history-row"
        latest_attr = ' aria-label="Latest trap"' if latest else ""
        return (
            f'<div class="{classes}"{latest_attr}>'
            f'<div class="trap-entry-head">'
            f'<strong style="color:{kind_color}">{escape(kind)}</strong>'
            f'<span class="trap-cause">{cause_name}</span>'
            f'<span class="trap-cycle">Cycle {cycle}</span>'
            f'</div>'
            f'<div class="trap-entry-meta">'
            f'<span>mepc 0x{mepc:08x}</span>'
            f'<span>mtvec 0x{mtvec:08x}</span>'
            f'<span>mtval 0x{mtval:08x}</span>'
            f'{priority_html}{halted_html}'
            f'</div></div>'
        )

    latest = render_entry(entries[-1], latest=True)
    older = "".join(render_entry(entry, latest=False) for entry in reversed(entries[:-1]))
    history = (
        f'<div class="trap-history-heading">Earlier traps</div>{older}'
        if older
        else ""
    )
    return f'<div class="trap-log">{latest}{history}</div>'


# ── Memory table ───────────────────────────────────────────────────────
def build_memory_table_html(
    mem,
    base_addr: int,
    rows: int,
    current_pc: int,
    changed_addresses: set[int] | None = None,
) -> str:
    changed = changed_addresses or set()
    header_cells = [
        f'<th class="state-marker-cell" aria-label="Program counter row" '
        f'style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:center;font-weight:500">PC</th>',
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;font-weight:500;white-space:nowrap">Address</th>',
    ]
    for i in range(16):
        header_cells.append(f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:center;font-weight:500;white-space:nowrap">+{i:X}</th>')
    header_cells.append(f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:left;font-weight:500;white-space:nowrap">ASCII</th>')

    row_strs = []
    for r in range(rows):
        addr = base_addr + r * 16
        is_pc_row = (current_pc & ~0xF) == addr
        bg = f"background:{C_CURRENT};" if is_pc_row else ""
        pc_marker = "▸" if is_pc_row else ""
        cells = [
            f'<td class="state-marker-cell" style="color:{C_ACCENT};padding:{_CELL_XS};'
            f'text-align:center"><span aria-hidden="true">{pc_marker}</span></td>',
            f'<td style="color:{C_ACCENT};padding:{_CELL_XS};text-align:right;white-space:nowrap">0x{addr:08x}</td>',
        ]
        ascii_chars = ""
        for col in range(16):
            byte_addr = addr + col
            byte_val = mem.peek_byte(byte_addr)
            is_changed = byte_addr in changed
            is_pc = is_pc_row and byte_addr == current_pc
            byte_color = C_GREEN if is_changed else (C_FG if byte_val != 0 else C_FG_DIM)
            cell_bg = f"background:{C_GREEN_SOFT};" if is_changed else ""
            weight = "font-weight:700;" if is_changed else ""
            if is_pc:
                byte_color = C_YELLOW
            classes = "memory-byte memory-byte-changed" if is_changed else "memory-byte"
            cells.append(
                f'<td class="{classes}" data-changed="{str(is_changed).lower()}" '
                f'style="{cell_bg}{weight}color:{byte_color};padding:{_CELL_XS};'
                f'text-align:center;font-family:monospace">{byte_val:02x}</td>'
            )
            ascii_chars += chr(byte_val) if 32 <= byte_val < 127 else "."
        cells.append(f'<td style="color:{C_FG_DIM};padding:{_CELL_XS};font-family:monospace;white-space:nowrap">{escape(ascii_chars)}</td>')
        pc_attr = ' aria-label="Program counter row"' if is_pc_row else ""
        row_strs.append(
            f'<tr data-pc-row="{str(is_pc_row).lower()}"{pc_attr} '
            f'style="{bg}{("font-weight:bold" if is_pc_row else "")}">'
            f'{"".join(cells)}</tr>'
        )

    return (
        f'<table class="memory-table" style="width:100%;border-collapse:collapse;font-size:11px;line-height:1.4">'
        f'<thead><tr style="background:{C_BG};border-bottom:1px solid {C_BORDER}">{"".join(header_cells)}</tr></thead>'
        f'<tbody>{"".join(row_strs)}</tbody></table>'
    )


def build_cache_table_html(cache, start_idx: int, num_lines: int, last_access=None, lookup_idx: int = -1) -> str:
    words_per_block = cache.words_per_block
    show_set_way = cache.ways > 1
    policy = getattr(cache, "policy", "fifo")
    show_repl = cache.ways > 1
    repl_header = "Age" if policy == "lru" else "Next"

    header_cells = [
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:left;font-weight:500;white-space:nowrap;width:48px">State</th>',
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;font-weight:500;white-space:nowrap;width:46px">Set</th>',
    ]
    if show_set_way:
        header_cells.append(
            f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;font-weight:500;white-space:nowrap;width:42px">Way</th>'
        )
    header_cells += [
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:center;font-weight:500;white-space:nowrap;width:30px">V</th>',
    ]
    if show_repl:
        header_cells.append(
            f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:center;font-weight:500;white-space:nowrap;width:44px">{repl_header}</th>'
        )
    header_cells += [
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;font-weight:500;white-space:nowrap;width:80px">Tag</th>',
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;font-weight:500;white-space:nowrap;width:104px">Block Addr</th>',
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:left;font-weight:500">Block Data</th>',
    ]

    row_strs = []
    index_shift = cache.index_shift
    tag_shift = cache.tag_shift
    num_sets = cache.num_sets
    ways = cache.ways
    for i in range(num_lines):
        idx = start_idx + i
        if idx >= num_sets * ways:
            break
        set_idx = idx // ways
        way_idx = idx % ways
        line = cache.sets[set_idx][way_idx]
        is_last = (
            last_access is not None
            and last_access.index == set_idx
            and (not show_set_way or last_access.way == way_idx)
        )
        is_lookup = (not show_set_way and idx == lookup_idx) or (
            show_set_way and set_idx == lookup_idx
        )
        bg = ""
        border = ""
        if is_last:
            bg = f"background:{C_CURRENT};"
        if is_lookup:
            border = f"border-left:2px solid {C_ACCENT};"
        valid_color = C_GREEN if line.valid else C_FG_DIM
        tag_color = C_ACCENT if line.valid else C_FG_DIM
        block_addr = (line.tag << tag_shift) | (set_idx << index_shift) if line.valid else 0
        block_color = C_CYAN if line.valid else C_FG_DIM

        markers = []
        state_labels = []
        if is_last:
            markers.append(
                f'<span class="cache-state-marker" style="color:{C_CYAN}" aria-label="Last access">A</span>'
            )
            state_labels.append("last access")
        if is_lookup:
            markers.append(
                f'<span class="cache-state-marker" style="color:{C_ACCENT}" aria-label="Lookup match">L</span>'
            )
            state_labels.append("lookup match")
        state_text = ", ".join(state_labels) if state_labels else "no state marker"
        marker_html = (
            "".join(markers)
            if markers
            else f'<span style="color:{C_FG_DIM}">-</span>'
        )
        cells = [
            f'<td style="padding:{_CELL_XS};text-align:left;white-space:nowrap">'
            f'{marker_html}</td>'
        ]
        # Set column (always shown). At ways==1 this is the old "Line" column.
        cells.append(
            f'<td style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;white-space:nowrap">{set_idx}</td>'
        )
        if show_set_way:
            cells.append(
                f'<td style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;white-space:nowrap">{way_idx}</td>'
            )
        cells += [
            f'<td style="color:{valid_color};padding:{_CELL_XS};text-align:center">{1 if line.valid else 0}</td>',
        ]
        if show_repl:
            if policy == "lru":
                age = cache._age[set_idx][way_idx]
                # Highlight the victim (age 0) red and the MRU (age == ways-1) green.
                if line.valid and age == 0:
                    repl_color = C_RED
                elif line.valid and age == ways - 1:
                    repl_color = C_GREEN
                else:
                    repl_color = C_FG_DIM
                repl_text = age if line.valid else "-"
            else:
                set_full = all(ln.valid for ln in cache.sets[set_idx])
                is_next = cache._victim[set_idx] == way_idx
                repl_text = cache._victim[set_idx] if (is_next and set_full) else "-"
                repl_color = C_RED if (is_next and set_full) else C_FG_DIM
            cells.append(
                f'<td style="color:{repl_color};padding:{_CELL_XS};text-align:center;font-family:monospace">{repl_text}</td>'
            )
        cells += [
            f'<td style="color:{tag_color};padding:{_CELL_XS};text-align:right;white-space:nowrap">0x{line.tag:05x}</td>',
            f'<td style="color:{block_color};padding:{_CELL_XS};text-align:right;white-space:nowrap">0x{block_addr:08x}</td>',
        ]
        word_items = []
        for w in range(words_per_block):
            off = w * WORD_BYTES
            word_val = int.from_bytes(line.data[off:off + WORD_BYTES], byteorder="little")
            word_color = C_GREEN if word_val != 0 and line.valid else C_FG_DIM
            word_items.append(
                f'<span class="cache-word" data-word-index="{w}" '
                f'aria-label="Word {w}: 0x{word_val:08x}">'
                f'<span class="cache-word-index">W{w:X}</span>'
                f'<span style="color:{word_color}">{word_val:08x}</span>'
                f'</span>'
            )
        cells.append(
            f'<td class="cache-data-cell" style="padding:{_CELL_XS}">'
            f'<div class="cache-word-grid">{"".join(word_items)}</div></td>'
        )

        row_strs.append(
            f'<tr data-last-access="{str(is_last).lower()}" '
            f'data-lookup-match="{str(is_lookup).lower()}" '
            f'aria-label="Set {set_idx}, way {way_idx}, {state_text}" '
            f'style="{bg}{border}">{"".join(cells)}</tr>'
        )

    return (
        f'<table class="cache-table" style="width:100%;border-collapse:collapse;font-size:11px;line-height:1.4">'
        f'<thead><tr style="background:{C_BG};border-bottom:1px solid {C_BORDER}">{"".join(header_cells)}</tr></thead>'
        f'<tbody>{"".join(row_strs)}</tbody></table>'
    )


# ── Cache access detail ────────────────────────────────────────────────
def build_cache_access_html(last_access, cache=None, cache_label: str | None = None) -> str:
    if last_access is None:
        return f'<div style="color:{C_FG_DIM};font-size:11px;padding:8px 0">No accesses yet</div>'

    addr = last_access.address
    tag = last_access.tag
    index = last_access.index
    wo = last_access.word_offset
    bo = last_access.byte_offset
    way = getattr(last_access, "way", -1)
    status = "HIT" if last_access.hit else "MISS"
    status_color = C_GREEN if last_access.hit else C_RED

    block_size = cache.block_size if cache is not None else 64
    tag_bits = cache.tag_bits if cache is not None else 17
    index_bits = cache.index_bits if cache is not None else 9
    offset_bits = cache.offset_bits if cache is not None else 6
    word_off_bits = offset_bits - 2
    ways = cache.ways if cache is not None else 1

    block_start = addr & ~(block_size - 1)  # align to block
    block_end = block_start + block_size - 1

    addr_bin = f"{addr:032b}"
    tag_part = addr_bin[:tag_bits]
    idx_part = addr_bin[tag_bits : tag_bits + index_bits] if index_bits else ""
    off_part = addr_bin[-offset_bits:]
    wo_bits = off_part[:word_off_bits] if word_off_bits else ""
    bo_bits = off_part[word_off_bits:]  # last 2 bits

    bit_spans = []
    for b in tag_part:
        bit_spans.append(f'<span style="background:{C_ACCENT_SOFT};color:{C_FG};padding:0 1px;border-radius:2px">{b}</span>')
    for b in idx_part:
        bit_spans.append(f'<span style="background:{C_YELLOW_SOFT};color:{C_FG};padding:0 1px;border-radius:2px">{b}</span>')
    for b in wo_bits:
        bit_spans.append(f'<span style="background:{C_GREEN_SOFT};color:{C_FG};padding:0 1px;border-radius:2px">{b}</span>')
    for b in bo_bits:
        bit_spans.append(f'<span style="background:{C_RED_SOFT};color:{C_FG};padding:0 1px;border-radius:2px">{b}</span>')

    index_label = "Index" if index_bits else "Index"
    index_display = f'{index}' if index_bits else "-"
    cache_name = f"{cache_label}-CACHE" if cache_label else "CACHE"
    set_way_extra = (
        f'<span>Way <strong style="color:{C_CYAN}">{way}</strong></span>'
        if ways > 1 and way >= 0
        else ""
    )

    repl_extra = ""
    if ways > 1 and way >= 0 and cache is not None:
        policy = getattr(cache, "policy", "fifo")
        if policy == "lru":
            age = cache._age[index][way]
            victim = next(
                (w for w in range(ways) if cache._age[index][w] == 0),
                -1,
            )
            repl_extra = (
                f'  <span style="color:{C_FG_DIM}">LRU: </span>'
                f'<span style="color:{C_FG}">age </span><span style="color:{C_CYAN}">{age}</span>'
                f'  <span style="color:{C_FG_DIM}">victim→</span><span style="color:{C_RED}">way {victim}</span>'
            )
        else:
            victim = cache._victim[index]
            repl_extra = (
                f'  <span style="color:{C_FG_DIM}">FIFO: </span>'
                f'<span style="color:{C_FG_DIM}">next victim→</span><span style="color:{C_RED}">way {victim}</span>'
            )

    tag_lbl = "tag" if tag_bits >= 3 else "t"
    idx_lbl = "index" if index_bits >= 5 else ("idx" if index_bits >= 3 else "i")
    idx_legend = (
        f'<span style="color:{C_YELLOW}">{" " * (index_bits - len(idx_lbl))}{idx_lbl}</span>'
        if index_bits
        else ""
    )

    return (
        f'<div class="cache-access-view" style="font-size:11px;line-height:1.6;padding:8px 0">'
        f'<div class="panel-context-band cache-access-context">'
        f'<div class="cache-access-primary">'
        f'<span class="cache-access-kind">{escape(cache_name)}</span>'
        f'<strong class="cache-access-address">0x{addr:08x}</strong>'
        f'<strong style="color:{status_color}">{status}</strong>'
        f'</div>'
        f'<div class="cache-access-meta">'
        f'<span>Set <strong style="color:{C_YELLOW}">{index_display}</strong></span>'
        f'{set_way_extra}'
        f'<span>Block <strong style="color:{C_CYAN}">0x{block_start:08x}-0x{block_end:08x}</strong></span>'
        f'</div></div>'
        f'<div class="cache-access-detail">'
        f'<div style="margin-bottom:6px">'
        f'<span style="color:{C_FG_DIM}">Tag: </span><span style="color:{C_ACCENT}">0x{tag:05x}</span>'
        f'  <span style="color:{C_FG_DIM}">{index_label}: </span><span style="color:{C_YELLOW}">{index_display}</span>'
        f'  <span style="color:{C_FG_DIM}">Word: </span><span style="color:{C_GREEN}">{wo}</span>'
        f'  <span style="color:{C_FG_DIM}">Byte: </span><span style="color:{C_RED}">{bo}</span>'
        f'{repl_extra}'
        f'</div>'
        f'<div style="font-family:monospace;letter-spacing:1px">'
        f'<span style="color:{C_FG_DIM}">[31]</span>'
        f'{"".join(bit_spans)}'
        f'<span style="color:{C_FG_DIM}">[0]</span>'
        f'</div>'
        f'<div style="font-family:monospace;letter-spacing:1px;color:{C_FG_DIM};font-size:10px">'
        f'<span style="color:{C_ACCENT}">{" " * (tag_bits - len(tag_lbl))}{tag_lbl}</span>'
        f'{idx_legend}'
        f'<span style="color:{C_GREEN}">{" " * max(word_off_bits - 2, 0)}wo</span>'
        f'<span style="color:{C_RED}">{" " * 1}bo</span>'
        f'</div>'
        f'</div></div>'
    )


# ── Cache stats (split L1) ─────────────────────────────────────────────
def build_cache_stats_html(istats: dict, dstats: dict) -> str:
    """Render a compact I/D/Combined stats table for the split L1 cache."""
    def row(label: str, s: dict, label_color: str, extra_style: str = "") -> str:
        acc = s["total_accesses"]
        hits = s["total_hits"]
        miss = s["total_misses"]
        rate = s["hit_rate"]
        mrate = 100.0 - rate if acc else 0.0
        # Color the rate: green when high, yellow mid, red low.
        if acc == 0:
            rc = C_FG_DIM
        elif rate >= 80:
            rc = C_GREEN
        elif rate >= 50:
            rc = C_YELLOW
        else:
            rc = C_RED
        return (
            f'<tr style="{extra_style}">'
            f'<td style="color:{label_color};padding:{_CELL_XS};font-weight:600;white-space:nowrap">{label}</td>'
            f'<td style="color:{C_FG};padding:{_CELL_XS};text-align:right;font-family:monospace">{acc}</td>'
            f'<td style="color:{C_GREEN};padding:{_CELL_XS};text-align:right;font-family:monospace">{hits}</td>'
            f'<td style="color:{C_RED};padding:{_CELL_XS};text-align:right;font-family:monospace">{miss}</td>'
            f'<td style="color:{rc};padding:{_CELL_XS};text-align:right;font-family:monospace;font-weight:600">{rate:.1f}%</td>'
            f'<td style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;font-family:monospace">{mrate:.1f}%</td>'
            f'</tr>'
        )

    # Combined totals.
    total_acc = istats["total_accesses"] + dstats["total_accesses"]
    total_hits = istats["total_hits"] + dstats["total_hits"]
    total_miss = istats["total_misses"] + dstats["total_misses"]
    combined = {
        "total_accesses": total_acc,
        "total_hits": total_hits,
        "total_misses": total_miss,
        "hit_rate": (total_hits / total_acc * 100) if total_acc else 0.0,
    }

    def th(text: str) -> str:
        return (
            f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;'
            f'font-weight:500;white-space:nowrap">{text}</th>'
        )

    return (
        f'<table style="width:100%;border-collapse:collapse;font-size:11px;line-height:1.4">'
        f'<thead><tr style="border-bottom:1px solid {C_BORDER}">'
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:left;font-weight:500"></th>'
        f'{th("Acc")}{th("Hit")}{th("Miss")}{th("Hit%")}{th("Miss%")}'
        f'</tr></thead>'
        f'<tbody>'
        f'{row("I-Cache", istats, C_CYAN)}'
        f'{row("D-Cache", dstats, C_ACCENT)}'
        f'{row("Total", combined, C_FG, extra_style=f"border-top:1px solid {C_BORDER}")}'
        f'</tbody></table>'
    )


# ── Assembly view ──────────────────────────────────────────────────────
def build_asm_view_html(
    asm_lines: list[str],
    pc_to_line: dict[int, int],
    current_pc: int,
    breakpoints: set[int],
) -> str:
    """Render the assembly listing with execution highlight and breakpoint markers."""
    if not asm_lines:
        return (
            '<div class="asm-empty">'
            "Compile a program to view its disassembly."
            "</div>"
        )

    target_line = pc_to_line.get(current_pc, -1)
    line_to_addr = {v: k for k, v in pc_to_line.items()}

    html_parts = [
        '<div class="asm-listing" role="region" aria-label="Program disassembly">',
        '<div class="asm-listing-head" aria-hidden="true">',
        '<span class="asm-head-bp">BP</span>',
        '<span class="asm-head-pc">PC</span>',
        '<span class="asm-head-instruction">Instruction</span>',
        "</div>",
    ]
    for i, line in enumerate(asm_lines):
        symbol_match = re.fullmatch(r"([0-9a-fA-F]+)\s+<(.+)>:", line)
        if symbol_match:
            symbol_addr = int(symbol_match.group(1), 16)
            symbol = escape(symbol_match.group(2), quote=True)
            html_parts.append(
                '<div class="asm-symbol">'
                '<div class="asm-symbol-meta">'
                '<span class="asm-symbol-kind">Label</span>'
                f'<span class="asm-symbol-address">0x{symbol_addr:08x}</span>'
                "</div>"
                f'<div class="asm-symbol-name">{symbol}</div>'
                "</div>"
            )
            continue

        instruction_match = re.fullmatch(
            r"\s*([0-9a-fA-F]+):\s*(\S+)(?:\s+(.*))?", line
        )
        addr = line_to_addr.get(i)
        if instruction_match:
            display_addr = int(instruction_match.group(1), 16)
            mnemonic = escape(instruction_match.group(2), quote=True)
            operands = escape(instruction_match.group(3) or "", quote=True)
        else:
            escaped = escape(line, quote=True)
            html_parts.append(f'<div class="asm-raw-line">{escaped}</div>')
            continue

        is_bp = addr is not None and addr in breakpoints
        is_current = i == target_line

        classes = ["asm-line"]
        if is_current:
            classes.append("asm-current")
        if is_bp:
            classes.append("asm-breakpoint")
        attrs = ""
        if addr is not None:
            attrs = (
                f' data-addr="{addr:08x}" role="button" tabindex="0"'
                f' aria-pressed="{"true" if is_bp else "false"}"'
                f' aria-label="Toggle breakpoint at 0x{addr:08x}"'
            )
        bp_marker = "\u25cf" if is_bp else ""
        pc_marker = "\u25b8" if is_current else ""
        html_parts.append(
            f'<div class="{" ".join(classes)}"{attrs}>'
            f'<span class="asm-bp-marker" aria-hidden="true">{bp_marker}</span>'
            f'<span class="asm-pc-marker" aria-hidden="true">{pc_marker}</span>'
            f'<span class="asm-address">0x{display_addr:08x}</span>'
            f'<span class="asm-mnemonic">{mnemonic}</span>'
            f'<span class="asm-operands">{operands}</span>'
            "</div>"
        )

    html_parts.append("</div>")
    return "\n".join(html_parts)


_STAGE_COLOR = {
    "IF": C_ACCENT,
    "ID": C_CYAN,
    "EX": C_GREEN,
    "MEM": C_YELLOW,
    "WB": C_ACCENT,
}


def build_state_legend_html(kind: str) -> str:
    """Render compact, visible state keys for the cache or pipeline."""
    if kind == "pipeline":
        items = (
            ("IF", "Fetch", C_ACCENT),
            ("ID", "Decode", C_CYAN),
            ("EX", "Execute", C_GREEN),
            ("MEM", "Memory", C_YELLOW),
            ("WB", "Writeback", C_ACCENT),
            ("*", "Current cycle", C_FG),
        )
    elif kind == "cache":
        items = (
            ("H", "Hit", C_GREEN),
            ("M", "Miss", C_RED),
            ("A", "Last access", C_CYAN),
            ("L", "Lookup match", C_ACCENT),
        )
    else:
        raise ValueError(f"unsupported state legend: {kind}")

    entries = "".join(
        f'<span class="state-legend-item" role="listitem">'
        f'<span class="state-legend-key" style="color:{color}">{key}</span>'
        f'<span>{label}</span></span>'
        for key, label, color in items
    )
    return (
        f'<div class="state-legend state-legend-{kind}" role="list" '
        f'aria-label="{kind.capitalize()} state legend">{entries}</div>'
    )


def format_branch_prediction_stats(stats) -> str:
    """Format detached branch-prediction counters for the Pipeline controls."""
    accuracy = stats.accuracy * 100 if stats.total else 0.0
    return (
        f"Branches {stats.total} | predicted T {stats.predicted_taken} / "
        f"NT {stats.predicted_not_taken} | correct {stats.correct} / "
        f"wrong {stats.incorrect} | accuracy {accuracy:.1f}%"
    )


def build_pipeline_latch_html(
    if_id=None,
    id_ex=None,
    ex_mem=None,
    mem_wb=None,
    mcycle: int = 0,
    minstret: int = 0,
    stalls: int = 0,
    flushes: int = 0,
) -> str:
    """Render pipeline latches and the IPC/stall/flush HUD."""
    cpi = (mcycle / minstret) if minstret else 0.0

    def latch_row(stage: str, l, color: str) -> str:
        if l is None or l.bubble:
            return (
                f'<tr>'
                f'<td style="color:{color};padding:{_CELL_XS};text-align:center;'
                f'font-family:monospace;font-weight:700;white-space:nowrap">{stage}</td>'
                f'<td style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;'
                f'font-family:monospace;white-space:nowrap">-</td>'
                f'<td style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:left;'
                f'font-family:monospace;font-style:italic;white-space:nowrap">bubble</td>'
                f'</tr>'
            )
        mnemonic = getattr(l, "mnemonic", None)
        if mnemonic is None:
            decoded = getattr(l, "decoded", None)
            mnemonic = decoded["inst_name"] if decoded else "?"
        return (
            f'<tr>'
            f'<td style="color:{color};padding:{_CELL_XS};text-align:center;'
            f'font-family:monospace;font-weight:700;white-space:nowrap">{stage}</td>'
            f'<td style="color:{C_ACCENT};padding:{_CELL_XS};text-align:right;'
            f'font-family:monospace;white-space:nowrap">0x{l.pc:08x}</td>'
            f'<td style="color:{C_FG};padding:{_CELL_XS};text-align:left;'
            f'font-family:monospace;white-space:nowrap">{mnemonic}</td>'
            f'</tr>'
        )

    header_cells = [
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:center;font-weight:500;white-space:nowrap">Stage</th>',
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:right;font-weight:500;white-space:nowrap">PC</th>',
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:left;font-weight:500;white-space:nowrap">Inst</th>',
    ]
    rows = [
        latch_row("IF/ID", if_id, _STAGE_COLOR["IF"]),
        latch_row("ID/EX", id_ex, _STAGE_COLOR["ID"]),
        latch_row("EX/MEM", ex_mem, _STAGE_COLOR["EX"]),
        latch_row("MEM/WB", mem_wb, _STAGE_COLOR["MEM"]),
    ]
    table = (
        f'<table class="pipeline-latches" style="border-collapse:collapse;font-size:11px;line-height:1.4">'
        f'<thead><tr style="background:{C_BG};border-bottom:1px solid {C_BORDER}">'
        f'{"".join(header_cells)}</tr></thead>'
        f'<tbody>{"".join(rows)}</tbody></table>'
    )
    hud = (
        f'<div class="pipeline-metrics" aria-label="Pipeline counters">'
        f'<span><small>mcycle</small><strong style="color:{C_CYAN}">{mcycle}</strong></span>'
        f'<span><small>minstret</small><strong style="color:{C_CYAN}">{minstret}</strong></span>'
        f'<span><small>CPI</small><strong style="color:{C_ACCENT}">{cpi:.2f}</strong></span>'
        f'<span><small>stalls</small><strong style="color:{C_YELLOW}">{stalls}</strong></span>'
        f'<span><small>flushes</small><strong style="color:{C_RED}">{flushes}</strong></span>'
        f'</div>'
    )
    return table + hud


def build_pipeline_gantt_html(
    trace: list[dict],
    window_cycles: int | None = None,
    max_rows: int | None = None,
) -> str:
    """Render the cycle-by-cycle pipeline trace as a Gantt grid."""
    if not trace:
        return f'<div style="color:{C_FG_DIM};font-size:12px;padding:8px">(not started - press Step in Pipeline mode)</div>'

    window = trace if window_cycles is None else trace[-window_cycles:]
    cycle_lo = window[0]["cycle"]
    cycle_hi = window[-1]["cycle"]
    clocks = [t["cycle"] for t in window]

    latch_chain = ("IF/ID", "ID/EX", "EX/MEM", "MEM/WB")
    latch_stage = {"IF/ID": "IF", "ID/EX": "ID", "EX/MEM": "EX", "MEM/WB": "MEM"}

    stalled_if_slots: dict[int, dict] = {}
    for index, t in enumerate(trace[:-1]):
        if t.get("hazard_stall_stage") != "ID":
            continue
        consumer = t["slots"].get("IF/ID")
        next_clock = trace[index + 1]
        younger = next_clock["slots"].get("IF/ID")
        next_cache_stall = next_clock.get("cache_stall")
        if younger is None and next_cache_stall is not None:
            if next_cache_stall.get("stage") == "IF":
                younger = next_cache_stall.get("slot")
        if (
            consumer is not None
            and younger is not None
            and younger.get("fetch_id") != consumer.get("fetch_id")
        ):
            stalled_if_slots[t["cycle"]] = younger

    def stage_slots(t: dict) -> dict[int, tuple[str, dict]]:
        """Return each visible stage's dynamic instruction."""
        stage_for_latch = latch_stage
        cache_stall = t.get("cache_stall")
        if cache_stall is not None and cache_stall.get("stage") == "MEM":
            stage_for_latch = {
                **latch_stage,
                "IF/ID": "ID",
                "ID/EX": "EX",
                "EX/MEM": "MEM",
            }
        elif t.get("hazard_stall_stage") == "ID":
            stage_for_latch = {**latch_stage, "IF/ID": "ID"}

        visible: dict[int, tuple[str, dict]] = {}
        for latch in latch_chain:
            slot = t["slots"].get(latch)
            if slot is not None and slot.get("fetch_id") is not None:
                visible[slot["fetch_id"]] = (stage_for_latch[latch], slot)

        if cache_stall is not None and cache_stall.get("stage") == "IF":
            slot = cache_stall.get("slot")
            if slot is not None and slot.get("fetch_id") is not None:
                visible[slot["fetch_id"]] = ("IF", slot)
        stalled_if = stalled_if_slots.get(t["cycle"])
        if stalled_if is not None and stalled_if.get("fetch_id") is not None:
            visible[stalled_if["fetch_id"]] = ("IF", stalled_if)
        return visible

    held_stalls: dict[tuple[int, int], str] = {}
    cache_stall_cells: dict[tuple[int, int], tuple[str, int, int]] = {}
    flushed_cells: dict[tuple[int, int], tuple[str, dict]] = {}
    previous_slots: dict[int, tuple[str, dict]] = {}
    analysis_trace = (
        trace
        if window_cycles is None
        else trace[-(window_cycles + 1):]
    )
    for t in analysis_trace:
        current_slots = stage_slots(t)
        cache_stall = t.get("cache_stall")
        if cache_stall is not None:
            slot = cache_stall.get("slot")
            if slot is not None and slot.get("fetch_id") is not None:
                cache_stall_cells[(slot["fetch_id"], t["cycle"])] = (
                    cache_stall["stage"],
                    cache_stall["index"],
                    cache_stall["total"],
                )
        elif t.get("hazard_stall_stage") == "ID":
            consumer = t["slots"].get("IF/ID")
            if consumer is not None and consumer.get("fetch_id") is not None:
                held_stalls[(consumer["fetch_id"], t["cycle"])] = "ID"
            stalled_if = stalled_if_slots.get(t["cycle"])
            if stalled_if is not None and stalled_if.get("fetch_id") is not None:
                held_stalls[(stalled_if["fetch_id"], t["cycle"])] = "IF"
        elif t.get("stall"):
            for fetch_id, (stage, _) in current_slots.items():
                previous = previous_slots.get(fetch_id)
                if previous is not None and previous[0] == stage:
                    held_stalls[(fetch_id, t["cycle"])] = stage
        if t.get("flush"):
            for fetch_id in previous_slots.keys() - current_slots.keys():
                if fetch_id == t.get("retired"):
                    continue
                flushed_cells[(fetch_id, t["cycle"])] = previous_slots[fetch_id]
        previous_slots = current_slots

    rows_by_id: dict[int, dict] = {}
    for t in window:
        c = t["cycle"]
        for fetch_id, (stage, slot) in stage_slots(t).items():
            row = rows_by_id.setdefault(fetch_id, {
                "key": fetch_id,
                "pc": slot["pc"],
                "mnem": slot["mnemonic"],
                "first_cycle": c,
                "cells": {},
            })
            row["cells"][c] = stage

        retired_id = t.get("retired")
        if retired_id is not None and retired_id in rows_by_id:
            rows_by_id[retired_id]["cells"][c] = "WB"

    visible_clocks = set(clocks)
    for (fetch_id, c), (_, slot) in flushed_cells.items():
        if c in visible_clocks:
            rows_by_id.setdefault(fetch_id, {
                "key": fetch_id,
                "pc": slot["pc"],
                "mnem": slot["mnemonic"],
                "first_cycle": c,
                "cells": {},
            })

    rows = sorted(rows_by_id.values(), key=lambda row: row["first_cycle"], reverse=True)
    if max_rows is not None:
        rows = rows[:max_rows]
    rows.sort(key=lambda row: row["first_cycle"])

    # Header: Inst | C{c}...
    header_cells = [
        f'<th style="color:{C_FG_DIM};padding:{_CELL_XS};text-align:left;font-weight:500;white-space:nowrap">Inst</th>',
    ]
    for c in clocks:
        current_attr = ' aria-current="true"' if c == cycle_hi else ""
        current_mark = "*" if c == cycle_hi else ""
        header_cells.append(
            f'<th data-cycle="{c}"{current_attr} style="color:{C_FG_DIM};padding:{_CELL_XS};'
            f'text-align:center;font-weight:500;white-space:nowrap">C{c}{current_mark}</th>'
        )

    highlight = cycle_hi  # the latest clock is "current"
    row_strs = []
    for row in rows:
        cells = [
            f'<td style="color:{C_ACCENT};padding:{_CELL_XS};text-align:left;font-family:monospace;white-space:nowrap">{row["mnem"]}</td>',
        ]
        for c in clocks:
            stage = row["cells"].get(c)
            is_cur = (c == highlight)
            bg = f"background:{C_CURRENT};" if is_cur else ""
            current_attr = ' aria-current="true"' if is_cur else ""
            if stage is None:
                flush_marker = flushed_cells.get((row["key"], c))
                if flush_marker is None:
                    cells.append(
                        f'<td data-cycle="{c}"{current_attr} '
                        f'style="{bg}padding:{_CELL_XS};text-align:center"></td>'
                    )
                else:
                    flushed_stage, _ = flush_marker
                    cells.append(
                        f'<td data-cycle="{c}" data-flush-stage="{flushed_stage}"{current_attr} '
                        f'aria-label="{row["mnem"]}, cycle {c}: flushed after {flushed_stage}" '
                        f'style="{bg}border-left:2px solid {C_RED};'
                        f'padding:{_CELL_XS};text-align:center"></td>'
                    )
            else:
                cache_marker = cache_stall_cells.get((row["key"], c))
                is_held_stall = held_stalls.get((row["key"], c)) == stage
                flushed_next = flushed_cells.get((row["key"], c + 1))
                flushed_style = ""
                if flushed_next is not None:
                    flushed_style = (
                        "text-decoration:line-through;"
                        "text-decoration-thickness:2px;"
                    )
                if cache_marker is not None:
                    stall_stage, index, total = cache_marker
                    label = stage
                    color = _STAGE_COLOR.get(stage, C_FG)
                    stall_attr = (
                        f' data-cache-stall-stage="{stall_stage}" '
                        f'data-stall-index="{index}" data-stall-total="{total}" '
                        f'aria-label="{row["mnem"]}, cycle {c}: {stall_stage} cache stall {index} of {total}"'
                    )
                elif is_held_stall:
                    label = stage
                    color = _STAGE_COLOR.get(stage, C_FG)
                    stall_attr = (
                        f' data-stall-stage="{stage}" '
                        f'aria-label="{row["mnem"]}, cycle {c}: held in {stage}"'
                    )
                else:
                    label = stage
                    color = _STAGE_COLOR.get(stage, C_FG)
                    stall_attr = (
                        f' data-stage="{stage}" '
                        f'aria-label="{row["mnem"]}, cycle {c}: {stage}"'
                    )
                if flushed_next is not None:
                    color = C_RED
                cells.append(
                    f'<td data-cycle="{c}"{current_attr}{stall_attr} style="{bg}{flushed_style}color:{color};padding:{_CELL_XS};'
                    f'text-align:center;font-family:monospace;font-weight:700;white-space:nowrap">{label}</td>'
                )
        row_strs.append(f'<tr data-fetch-id="{row["key"]}">{"".join(cells)}</tr>')

    footer = (
        f'<div style="margin-top:4px;font-size:10px;font-family:monospace;color:{C_FG_DIM}">'
        f'cycles {cycle_lo}-{cycle_hi} | {len(rows)} instruction(s) shown'
        f'</div>'
    )
    return (
        f'<table class="pipeline-gantt" style="border-collapse:collapse;font-size:10px;line-height:1.3">'
        f'<thead><tr style="background:{C_BG};border-bottom:1px solid {C_BORDER}">{"".join(header_cells)}</tr></thead>'
        f'<tbody>{"".join(row_strs)}</tbody></table>'
        + footer
    )


def build_mc_stage_html(
    pc: int | None = None,
    mnemonic: str | None = None,
    stages: list[str] | None = None,
    active_idx: int = -1,
    mcycle: int = 0,
    minstret: int = 0,
    inst_size: int = 4,
    error: str | None = None,
    stall_info: tuple[str, int] | None = None,
) -> str:
    """Render one variable-length multi-cycle stage walk and live CPI."""
    if error is not None:
        return (
            f'<div style="color:{C_RED};font-size:12px;padding:6px;font-family:monospace">'
            f'[MC engine error] {escape(error)}</div>'
        )

    cpi = (mcycle / minstret) if minstret else 0.0

    if stages is None or pc is None:
        return (
            f'<div style="color:{C_FG_DIM};font-size:12px;padding:8px;font-family:monospace">'
            f'(idle - press Step to fetch the next instruction)<br>'
            f'<span style="color:{C_CYAN}">mcycle={mcycle}</span> &nbsp; '
            f'<span style="color:{C_CYAN}">minstret={minstret}</span> &nbsp; '
            f'<span style="color:{C_ACCENT}">CPI={cpi:.2f}</span>'
            f'</div>'
        )

    def stage_cell(i: int, s: str) -> str:
        stall_badge = ""
        if stall_info is not None and s == stall_info[0]:
            n = stall_info[1]
            stall_badge = (
                f' <span class="mc-stall-badge">STALL({n})</span>'
            )
        if i == active_idx:
            return (
                f'<span class="mc-stage mc-stage-active" role="listitem" '
                f'aria-current="step" style="color:{C_FG}">{s}{stall_badge}</span>'
            )
        if i < active_idx:
            return (
                f'<span class="mc-stage mc-stage-complete" role="listitem" '
                f'style="color:{_STAGE_COLOR.get(s, C_FG)}">{s}{stall_badge}</span>'
            )
        return (
            f'<span class="mc-stage mc-stage-future" role="listitem" '
            f'style="color:{C_FG_DIM}">{s}</span>'
        )

    clock_str = f"{active_idx + 1}/{len(stages)}" if active_idx >= 0 else f"0/{len(stages)}"
    stage_cells = "".join(stage_cell(i, s) for i, s in enumerate(stages))

    return (
        f'<div class="mc-view">'
        f'<div class="panel-context-band mc-context">'
        f'<div class="mc-context-main">'
        f'<strong class="mc-mnemonic">{escape(str(mnemonic))}</strong>'
        f'<span class="mc-pc">0x{pc:08x}</span>'
        f'<span>{inst_size}B</span>'
        f'</div>'
        f'<div class="mc-context-meta">'
        f'<span>Clock <strong style="color:{C_GREEN}">{clock_str}</strong></span>'
        f'<span>mcycle <strong style="color:{C_CYAN}">{mcycle}</strong></span>'
        f'<span>minstret <strong style="color:{C_CYAN}">{minstret}</strong></span>'
        f'<span>CPI <strong style="color:{C_ACCENT}">{cpi:.2f}</strong></span>'
        f'</div></div>'
        f'<div class="mc-stage-label">Stage progress</div>'
        f'<div class="mc-stage-track" role="list" aria-label="Multi-cycle stage progress">'
        f'{stage_cells}</div></div>'
    )
