"""Cache behavior across supported geometry combinations."""

import pytest

from rv32i.memory import Memory
from rv32i.cache import Cache, CacheGeometry

@pytest.fixture
def mem():
    return Memory()


def make(total_size=4 * 1024, block_size=64, ways=1, mem=None, policy="fifo"):
    return Cache(mem or Memory(), total_size, block_size, ways, policy)


# Curated matrix covering each geometry axis and its boundary cases.
_SIZES = (1024, 4096, 8192, 16384, 32768, 65536, 131072, 262144)
_BLOCKS = (16, 32, 64, 128)
_WAYS = (1, 2, 4, 8, 16)


def try_geometry(s, b, w):
    try:
        return CacheGeometry.from_size(s, b, w)
    except ValueError:
        return None


VALID_GEOMETRIES = [
    (s, b, w)
    for s in _SIZES
    for b in _BLOCKS
    for w in _WAYS
    if try_geometry(s, b, w) is not None
]

# Readable pytest ids: "4K_b64_w4".
GEOM_IDS = [f"{s//1024}K_b{b}_w{w}" for (s, b, w) in VALID_GEOMETRIES]

# Smaller geometries only — used by the capacity-miss test, which streams
# num_lines+1 distinct blocks; keeping num_lines small keeps the test fast.
SMALL_GEOMETRIES = [(s, b, w) for (s, b, w) in VALID_GEOMETRIES if s <= 4096]
SMALL_IDS = [f"{s//1024}K_b{b}_w{w}" for (s, b, w) in SMALL_GEOMETRIES]


def geometry(size, block, ways) -> CacheGeometry:
    return CacheGeometry.from_size(size, block, ways)


def set_zero_addresses(geom: CacheGeometry, n: int) -> list[int]:
    """`n` addresses that all map to set 0 with distinct tags.

    stride = block_size * num_sets = 2**(offset_bits + index_bits), so the
    set-index field is always 0 and each address's tag is exactly its index k.
    """
    stride = geom.block_size * geom.num_sets
    return [k * stride for k in range(n)]


def tag_of(c: Cache, addr: int) -> int:
    return c.parse_address(addr)[0]


# ── 1. geometry sweep: self-consistency across the whole matrix ──────────

@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_geometry_self_consistent(size, block, ways):
    g = geometry(size, block, ways)
    # capacity identity
    assert g.num_sets * g.ways * g.block_size == g.total_size == size
    assert g.num_lines == g.num_sets * g.ways == size // block
    # address split partitions all 32 bits
    assert g.tag_bits + g.index_bits + g.offset_bits == 32
    assert g.words_per_block == block // 4
    # derived fields match their definitions
    assert g.offset_bits == g.block_size.bit_length() - 1
    assert g.index_bits == g.num_sets.bit_length() - 1
    assert g.word_offset_bits == g.offset_bits - 2


@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_set_index_of_round_trips(size, block, ways, mem):
    """The public set_index_of(addr) must match the internal parse_address split."""
    c = make(size, block, ways, mem)
    for addr in (0, 0x40, 0x1000, 0x1FFFFF, 0x80000000, 0x7C, 0x12345670):
        addr &= 0xFFFFFFFF
        internal = c.parse_address(addr)[1]
        assert c.set_index_of(addr) == internal


@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_lines_flat_view_matches_sets(size, block, ways, mem):
    """The flat `lines` view is set-major: lines[set*ways + way] is sets[set][way]."""
    c = make(size, block, ways, mem)
    assert len(c.lines) == c.num_sets * c.ways
    for s in range(c.num_sets):
        for w in range(c.ways):
            assert c.lines[s * c.ways + w] is c.sets[s][w]


# ── 2. the 3 C's of cache misses + hits ──────────────────────────────────

@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_compulsory_miss_then_hit(size, block, ways, mem):
    """A cold (compulsory) miss on first touch, a hit on the immediate re-read."""
    c = make(size, block, ways, mem)
    g = c.geom
    a = set_zero_addresses(g, 1)[0]
    c.mem.write_word(a, 0xCAFEBABE)

    assert c.read_word(a) == 0xCAFEBABE   # compulsory miss
    assert c.total_misses == 1
    assert c.read_word(a) == 0xCAFEBABE   # hit
    assert c.total_hits == 1


@pytest.mark.parametrize("size,block,ways", SMALL_GEOMETRIES, ids=SMALL_IDS)
def test_capacity_miss(size, block, ways, mem):
    """A capacity miss: streaming more *distinct* blocks than the cache holds
    evicts the very first block, so re-reading it misses even though it was
    once resident.

    Touching every set in order (stride = block_size) fills the whole cache;
    block k maps to set (k mod num_sets). Block `num_lines` maps to set 0 and,
    because we streamed in ascending order, block 0 is the oldest / LRU line
    in set 0 under BOTH policies → it is the eviction victim.
    """
    c = make(size, block, ways, mem)
    n = c.num_lines + 1            # one more distinct block than the cache holds
    addrs = [i * block for i in range(n)]
    for a in addrs:
        c.mem.write_word(a, a | 0xF000)

    for a in addrs:                # fill the cache + force one eviction
        c.read_word(a)

    before = c.total_misses
    c.read_word(addrs[0])          # block 0 was evicted by capacity
    assert c.total_misses == before + 1


@pytest.mark.parametrize("ways", [1, 2, 4, 8, 16])
def test_conflict_miss_thrash(ways, mem):
    """Two blocks mapping to the same set, alternated.

    * 1-way (direct-mapped): the two aliases evict each other every time, so
      the two re-reads both MISS — conflict thrashing.
    * N≥2-way: both aliases coexist, so the two re-reads both HIT — this is
      exactly the conflict misses that associativity exists to remove.
    """
    # Single set (total = block*ways) so both addresses unambiguously alias.
    c = make(ways * 64, 64, ways, mem)
    g = c.geom
    a, b = set_zero_addresses(g, 2)
    c.mem.write_word(a, 0xAAAA)
    c.mem.write_word(b, 0xBBBB)

    c.read_word(a)                 # miss
    c.read_word(b)                 # miss
    c.read_word(a)                 # 1-way: miss (evicted); N-way: hit
    c.read_word(b)                 # 1-way: miss (evicted); N-way: hit

    expected_hits = 0 if ways == 1 else 2
    assert c.total_hits == expected_hits


@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_hit_after_fill_no_eviction(size, block, ways, mem):
    """Re-reading a resident block hits and must not evict any neighbor.

    a and b are placed so they coexist for EVERY geometry: different sets when
    num_sets > 1, or (since num_sets==1 implies ways>=2) two tags in the one
    shared set otherwise. Either way, hitting a repeatedly never evicts b.
    """
    c = make(size, block, ways, mem)
    g = c.geom
    if g.num_sets > 1:
        a, b = 0, g.block_size            # set 0 and set 1 — guaranteed non-aliasing
    else:
        a, b = set_zero_addresses(g, 2)          # one set, ways>=2 → both fit
    c.mem.write_word(a, 0x1111)
    c.mem.write_word(b, 0x2222)

    c.read_word(a)                 # miss, fill
    c.read_word(b)                 # miss, fill
    for _ in range(5):
        assert c.read_word(a) == 0x1111   # always a hit
    assert c.total_hits == 5
    # b is still resident (the hits on a never evicted it).
    before = c.total_hits
    c.read_word(b)
    assert c.total_hits == before + 1


# ── 3. cross-cutting correctness ────────────────────────────────────────

@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_stats_invariant(size, block, ways, mem):
    """accesses == hits + misses always, and hit_rate is the documented ratio."""
    c = make(size, block, ways, mem)
    g = c.geom
    for a in set_zero_addresses(g, 4):
        c.mem.write_word(a, a + 1)
    # a mix of misses and hits
    for a in set_zero_addresses(g, 4):
        c.read_word(a)
    c.read_word(set_zero_addresses(g, 4)[0])     # one hit

    st = c.get_stats()
    assert st["total_accesses"] == c.total_accesses
    assert st["total_hits"] + st["total_misses"] == st["total_accesses"]
    expected_rate = st["total_hits"] / st["total_accesses"] * 100
    assert st["hit_rate"] == pytest.approx(expected_rate)


def test_stats_hit_rate_zero_when_empty(mem):
    """No accesses → hit_rate is 0.0 (no division by zero)."""
    c = make(4096, 64, 1, mem)
    assert c.get_stats()["hit_rate"] == 0.0


@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_last_access_fields_on_hit_and_miss(size, block, ways, mem):
    """CacheAccess records the correct {tag,index,word_offset,byte_offset,hit,way}."""
    c = make(size, block, ways, mem)
    g = c.geom
    a = set_zero_addresses(g, 1)[0]
    c.mem.write_word(a, 0xDEAD)

    # --- miss ---
    c.read_word(a)
    la = c.last_access
    assert la.address == a
    assert la.tag == tag_of(c, a)
    assert la.index == 0                     # set_zero_addresses → set 0
    assert la.hit is False
    assert la.way == c.find_way(0, la.tag)  # the way it was filled into
    assert la.way >= 0

    # --- hit ---
    c.read_word(a)
    la = c.last_access
    assert la.hit is True
    assert la.way == c.find_way(0, la.tag)


@pytest.mark.parametrize("block", [16, 32, 64, 128])
def test_all_widths_roundtrip_signed_and_unsigned(block, mem):
    """byte/halfword/word writes round-trip through reads at every block size,
    including sign-extension on lb/lh."""
    c = make(4 * 1024, block, 1, mem)
    c.mem.write_word(0, 0x807F00FF)          # byte3..0 = 80,7F,00,FF

    assert c.read_word(0) == 0x807F00FF
    assert c.read_halfword(0) == 0x00FF
    assert c.read_halfword(2) == 0x807F
    assert c.read_byte(0) == 0xFF
    assert c.read_byte(1) == 0x00
    assert c.read_byte(2) == 0x7F
    assert c.read_byte(3) == 0x80
    # signed loads sign-extend the high bit of the loaded field. The cache
    # returns Python ints (arbitrary precision), so signed values are true
    # negatives, not masked 32-bit patterns.
    assert c.read_byte(0, signed=True) == -1              # 0xFF → -1
    assert c.read_byte(3, signed=True) == -128            # 0x80 → -128
    assert c.read_halfword(2, signed=True) == -0x7F81     # 0x807F → -32641


@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_within_block_offsets_correct(size, block, ways, mem):
    """Every word (and byte) offset inside a block reads back the value written,
    proving the word_offset/byte_offset decode is correct at this geometry."""
    c = make(size, block, ways, mem)
    base = set_zero_addresses(c.geom, 1)[0]
    # Fill each word of the block with a distinct, recoverable value.
    for woff in range(c.words_per_block):
        c.mem.write_word(base + woff * 4, (woff * 31 + 7) & 0xFFFFFFFF)

    for woff in range(c.words_per_block):
        addr = base + woff * 4
        assert c.read_word(addr) == (woff * 31 + 7) & 0xFFFFFFFF
    # Spot-check byte offsets within word 0. The block is resident, so write
    # THROUGH the cache (a direct mem.write_byte would leave the cached line
    # stale — that's the write-through contract, not an offset-decode bug).
    c.write_byte(base, 0xAB)
    assert c.read_byte(base) == 0xAB
    assert c.read_byte(base + 1) == (((0 * 31 + 7) & 0xFFFFFFFF) >> 8) & 0xFF


@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_write_through_and_allocate(size, block, ways, mem):
    """A store is write-through (memory updated) AND write-allocate (block
    brought in), so an immediate reload hits."""
    c = make(size, block, ways, mem)
    a = set_zero_addresses(c.geom, 1)[0]

    c.write_word(a, 0xDEADBEEF)
    # write-through
    assert c.mem.read_word(a) == 0xDEADBEEF
    # write-allocate → resident → reload hits
    before = c.total_hits
    assert c.read_word(a) == 0xDEADBEEF
    assert c.total_hits == before + 1


@pytest.mark.parametrize("size,block,ways", VALID_GEOMETRIES, ids=GEOM_IDS)
def test_flush_zeroes_everything(size, block, ways, mem):
    """flush() invalidates all sets/ways, resets replacement + stats, clears last_access."""
    c = make(size, block, ways, mem)
    for a in set_zero_addresses(c.geom, min(c.ways, 4)):
        c.mem.write_word(a, a | 0xF000)
        c.read_word(a)
    assert c.total_accesses > 0
    assert c.last_access is not None

    c.flush()
    assert all(not line.valid for s in c.sets for line in s)
    assert all(v == 0 for v in c._victim)
    assert all(age == 0 for row in c._age for age in row)
    assert c.total_accesses == c.total_hits == c.total_misses == 0
    assert c.last_access is None


def test_device_access_bypasses_lines(mem):
    """A device (MMIO) access is recorded as a miss with way==-1 and must NOT
    populate any cache line — device state can never be cached."""
    c = make(1024, 64, 1, mem)
    # Register a trivial device at 0x10000000.
    DEV = 0x10000000
    mem.register_device("dev", DEV, 16, on_read=lambda addr, size: 0xABCDEF01, on_write=lambda *a: None)

    val = c.read_word(DEV)
    assert val == 0xABCDEF01
    la = c.last_access
    assert la.hit is False
    assert la.way == -1                       # bypass marker
    # No line for the device's set was populated.
    assert all(not line.valid for s in c.sets for line in s)


# ── 4. policy contrast ──────────────────────────────────────────────────

def test_fifo_and_lru_identical_at_one_way(mem):
    """At ways==1 there is only one line per set, so the policy is irrelevant:
    FIFO and LRU produce identical miss counts on the same access stream."""
    g = geometry(1024, 64, 1)
    addrs = set_zero_addresses(g, 3)

    def run(policy):
        c = make(1024, 64, 1, mem, policy=policy)
        for a in addrs:
            c.mem.write_word(a, a | 0xF000)
        for a in addrs:
            c.read_word(a)
        c.read_word(addrs[0])
        return c.total_misses

    assert run("fifo") == run("lru")


@pytest.mark.parametrize("ways", [2, 4])
def test_fifo_and_lru_diverge_at_n_way(ways, mem):
    """The canonical policy contrast on a single set, scaled to N ways.

    Fill the set with N distinct tags, re-access tag 0, then insert one more
    distinct tag → exactly one forced eviction. The re-accessed tag 0 is the
    deciding line:
        LRU  evicts tag 1 (tag 0 was just re-used → it is the MRU, so the
             oldest *unre-used* line, tag 1, is the victim; tag 0 survives),
        FIFO evicts tag 0 (insertion order; the re-use is irrelevant, so the
             oldest-inserted line is the victim; tag 0 is evicted).
    """
    g = geometry(ways * 64, 64, ways)            # exactly one set
    tags = set_zero_addresses(g, ways + 1)           # ways fill + 1 to force eviction
    tag0, intruder = tags[0], tags[-1]

    def run(policy):
        cache = make(ways * 64, 64, ways, mem, policy=policy)
        for x in tags:
            cache.mem.write_word(x, x | 0xF000)
        for x in tags[:ways]:                 # fill all ways
            cache.read_word(x)
        cache.read_word(tag0)                 # re-use tag 0 (LRU: MRU; FIFO: ignored)
        cache.read_word(intruder)             # full-set miss → one eviction
        return cache

    lru = run("lru")
    fifo = run("fifo")
    # LRU kept tag 0 (re-used), evicted tag 1 (oldest unre-used).
    assert lru.find_way(0, tag_of(lru, tag0)) != -1
    assert lru.find_way(0, tag_of(lru, tags[1])) == -1
    # FIFO evicted tag 0 (oldest insertion), kept tag 1.
    assert fifo.find_way(0, tag_of(fifo, tag0)) == -1
    assert fifo.find_way(0, tag_of(fifo, tags[1])) != -1
