"""Split instruction/data cache behavior and accounting."""

import pytest

from rv32i.memory import Memory
from rv32i.cache import DirectMappedCache, BLOCK_SIZE


# ── fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mem():
    return Memory()


@pytest.fixture
def icache(mem):
    return DirectMappedCache(mem)


@pytest.fixture
def dcache(mem):
    return DirectMappedCache(mem)


# ── fetch accounting: 1 access per instruction ─────────────────────────

def test_fetch_32bit_is_one_access(icache):
    """A 32-bit instruction costs exactly one cache access (its low half)."""
    icache.mem.write_word(0x100, 0x00000013 | 0x3)  # low nibble 0x3 -> 4-byte
    before = icache.total_accesses
    inst, size = icache.fetch_instruction(0x100)
    assert size == 4
    assert icache.total_accesses == before + 1


def test_fetch_rvc_16bit_is_one_access(icache):
    """A 16-bit (RVC) instruction also costs exactly one access."""
    icache.mem.write_halfword(0x200, 0x0001)
    before = icache.total_accesses
    inst, size = icache.fetch_instruction(0x200)
    assert size == 2
    assert icache.total_accesses == before + 1


def test_two_rvc_are_two_accesses(icache):
    """
    Two adjacent 16-bit instructions cost two accesses — one per instruction.
    No buffer means no sharing, even though both live in the same word.
    """
    icache.mem.write_word(0x300, 0x00020001)
    icache.fetch_instruction(0x300)   # RVC #1
    icache.fetch_instruction(0x302)   # RVC #2 (different instruction)
    assert icache.total_accesses == 2


def test_straddle_is_one_access(icache):
    """
    A 32-bit instruction straddling a 4-byte word boundary still costs only
    one access: the low-half fetch loads the line, and the upper half is
    read directly from the resident line (no second counted access).
    """
    inst32 = (0xABCD << 16) | 0x0013  # bits[1:0]==0b11 -> 4-byte
    icache.mem.write_halfword(0x502, inst32 & 0xFFFF)
    icache.mem.write_halfword(0x504, (inst32 >> 16) & 0xFFFF)

    inst, size = icache.fetch_instruction(0x502)
    assert size == 4
    assert inst == inst32
    assert icache.total_accesses == 1
    assert icache.total_misses == 1   # cold block


def test_straddle_decodes_correctly(icache):
    """Straddle must produce the correct 32-bit instruction value."""
    inst32 = 0xDEADBEEF | 0x3        # ensure low bits 0b11 -> 4-byte
    icache.mem.write_halfword(0x602, inst32 & 0xFFFF)
    icache.mem.write_halfword(0x604, (inst32 >> 16) & 0xFFFF)
    inst, size = icache.fetch_instruction(0x602)
    assert inst == inst32
    assert size == 4


def test_repeated_fetch_same_pc_is_two_accesses(icache):
    """
    Without a buffer, fetching the same address twice costs two accesses
    (the second is a hit). This confirms there's no buffer caching the word.
    """
    icache.mem.write_halfword(0x700, 0x0001)
    icache.fetch_instruction(0x700)
    icache.fetch_instruction(0x700)
    assert icache.total_accesses == 2
    assert icache.total_hits == 1     # second fetch hits
    assert icache.total_misses == 1   # first fetch misses


# ── independence ────────────────────────────────────────────────────────

def test_icache_and_dcache_are_independent(mem, icache, dcache):
    """Fetching an address must NOT populate the D-cache, and vice versa."""
    mem.write_word(0x1000, 0x00000033)

    icache.fetch_instruction(0x1000)
    assert icache.total_accesses >= 1
    assert dcache.total_accesses == 0

    INDEX_SHIFT = 6
    INDEX_MASK = 0x1FF
    idx = (0x1000 >> INDEX_SHIFT) & INDEX_MASK
    assert dcache.lines[idx].valid is False
    assert icache.lines[idx].valid is True


def test_dcache_access_does_not_touch_icache(mem, icache, dcache):
    mem.write_word(0x2000, 0xDEADBEEF)
    val = dcache.read_word(0x2000)
    assert val == 0xDEADBEEF
    assert dcache.total_accesses == 1
    assert icache.total_accesses == 0


# ── flush ───────────────────────────────────────────────────────────────

def test_flush_is_per_instance(mem, icache, dcache):
    """Flushing one cache must not clear the other."""
    mem.write_word(0x3000, 0x11223344)
    icache.fetch_instruction(0x3000)
    dcache.read_word(0x3000)

    icache.flush()
    assert icache.total_accesses == 0
    assert icache.last_access is None
    assert dcache.total_accesses == 1  # untouched


def test_flush_resets_stats(icache):
    """flush() zeroes all counters and clears lines."""
    icache.mem.write_word(0x400, 0x00000033)
    icache.fetch_instruction(0x400)
    assert icache.total_accesses > 0

    icache.flush()
    assert icache.total_accesses == 0
    assert icache.total_hits == 0
    assert icache.total_misses == 0
    assert all(not line.valid for line in icache.lines)


# ── RV32C block-boundary straddle (regression) ──────────────────────────

def test_fetch_straddling_block_boundary(mem, icache):
    """
    A 32-bit instruction at the last 2 bytes of a 64-byte block straddles
    into the next block. The low-half access misses (loads block N), then
    the upper half lives in block N+1 — a different line — so the fallback
    read_halfword is used and counts a second access (also a miss).
    """
    base = 0x10000
    straddle_addr = base + BLOCK_SIZE - 2
    assert straddle_addr % BLOCK_SIZE == BLOCK_SIZE - 2

    inst32 = (0xABCD << 16) | 0x0013  # bits[1:0]==0b11 -> 4-byte
    mem.write_halfword(straddle_addr, inst32 & 0xFFFF)
    mem.write_halfword(straddle_addr + 2, (inst32 >> 16) & 0xFFFF)

    inst, size = icache.fetch_instruction(straddle_addr)
    assert size == 4
    assert inst == inst32
    # Low half in block N (miss), upper half in block N+1 — the fallback
    # path counts a second access because the line there is NOT resident.
    assert icache.total_accesses == 2
    assert icache.total_misses == 2
