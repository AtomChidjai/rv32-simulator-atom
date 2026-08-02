"""Cache geometry, associativity, and replacement-policy tests."""

import pytest

from rv32i.memory import Memory
from rv32i.cache import Cache, CacheGeometry, DirectMappedCache


# ── fixtures ────────────────────────────────────────────────────────────

@pytest.fixture
def mem():
    return Memory()


def make(total_size=32 * 1024, block_size=64, ways=1, mem=None, policy="fifo"):
    return Cache(mem or Memory(), total_size, block_size, ways, policy)


# ── geometry validation ─────────────────────────────────────────────────

def test_geometry_default_matches_original():
    """Default Cache() reproduces the original 32 KB / 64 B / 1-way geometry."""
    g = CacheGeometry.from_size(32 * 1024, 64, 1)
    assert (g.num_sets, g.num_lines, g.ways, g.block_size) == (512, 512, 1, 64)
    assert (g.tag_bits, g.index_bits, g.offset_bits) == (17, 9, 6)
    assert g.words_per_block == 16


@pytest.mark.parametrize("ways,exp_sets", [(1, 512), (2, 256), (4, 128), (8, 64), (16, 32)])
def test_geometry_ways_splits_sets(ways, exp_sets):
    """At 32 KB / 64 B, total lines stay 512; sets = 512 / ways."""
    c = make(32 * 1024, 64, ways)
    assert c.num_lines == 512
    assert c.num_sets == exp_sets
    assert len(c.sets) == exp_sets
    assert all(len(s) == ways for s in c.sets)
    # tag grows as index shrinks; offset fixed at 6.
    assert c.offset_bits == 6
    assert c.tag_bits + c.index_bits == 32 - 6


@pytest.mark.parametrize("block,exp_off", [(16, 4), (32, 5), (64, 6), (128, 7)])
def test_geometry_block_sizes(block, exp_off):
    c = make(8 * 1024, block, 1)
    assert c.offset_bits == exp_off
    assert c.words_per_block == block // 4
    assert c.num_lines == (8 * 1024) // block


def test_geometry_fully_associative_one_set():
    """1 KB / 64 B / 16-way → exactly 1 set (index_bits == 0)."""
    c = make(1024, 64, 16)
    assert c.num_sets == 1
    assert c.index_bits == 0
    assert c.index_mask == 0
    assert c.tag_bits == 32 - 6  # all bits above offset are tag


def test_geometry_rejects_bad_inputs():
    # Note: the core Cache allows any power-of-two block >= WORD_BYTES (4), so
    # e.g. an 8 B block is structurally valid. The GUI's preset dropdown
    # (16/32/64/128) is the stricter layer. These cases are invalid at the
    # core structural level.
    for args in [
        (300, 64, 1),    # size not power of two
        (1024, 64, 3),   # ways not in 1/2/4/8/16
        (64, 2, 1),      # block < WORD_BYTES (4)
        (64, 3, 1),      # block not power of two
        (128, 64, 4),    # 128 < 64*4 → not divisible → num_sets < 1
    ]:
        with pytest.raises(ValueError):
            make(*args)


# ── 1-way / default parity with original behavior ───────────────────────

def test_one_way_acts_direct_mapped(mem):
    """1-way: a block maps to exactly one line; re-reads of evicted blocks miss."""
    c = make(1024, 64, 1, mem)  # 16 sets
    # Two addresses that map to the same set (set 0) but different tags.
    a0 = 0x000  # set 0, tag 0
    a1 = 0x400  # set 0, tag 1 (0x400 >> 6 = 16 = set 0 mod 16)
    c.mem.write_word(a0, 0xAAAA0000)
    c.mem.write_word(a1, 0xBBBB0000)

    assert c.read_word(a0) == 0xAAAA0000  # miss, fill
    assert c.read_word(a0) == 0xAAAA0000  # hit
    assert c.read_word(a1) == 0xBBBB0000  # miss, evicts a0's line
    assert c.read_word(a0) == 0xAAAA0000  # miss again (evicted) — direct-mapped

    # The last read reloaded a0, so it should now hit.
    assert c.read_word(a0) == 0xAAAA0000  # hit


def test_alias_direct_mapped_cache_still_works(mem):
    """DirectMappedCache alias == Cache with default args."""
    c1 = DirectMappedCache(mem)
    c2 = Cache(mem)
    assert c1.num_sets == c2.num_sets
    assert c1.num_lines == c2.num_lines


# ── ways>1 correctness + round-robin ────────────────────────────────────

def test_two_way_keeps_both_conflicting_blocks(mem):
    """2-way: two blocks mapping to the same set both stay resident."""
    c = make(1024, 64, 2, mem)  # 8 sets, 2 ways
    a0 = 0x000
    a1 = 0x400  # same set as a0 (0x400>>6=16, 16 mod 8 = 0), different tag
    c.mem.write_word(a0, 0xAAAA0000)
    c.mem.write_word(a1, 0xBBBB0000)

    c.read_word(a0)  # miss, fill way0
    c.read_word(a1)  # miss, fill way1 (set not full → no eviction)
    assert c.total_misses == 2

    # Both should now hit — 2-way absorbed both without eviction.
    c.read_word(a0)
    c.read_word(a1)
    assert c.total_hits == 2
    assert c.total_misses == 2


def test_round_robin_evicts_oldest_way(mem):
    """Full-set miss evicts round-robin: pointer advances 0→1→0…"""
    c = make(1024, 64, 2, mem)  # 8 sets, 2 ways
    set0_blocks = [0x000, 0x400]            # two tags in set 0
    intruder = 0x800                       # third tag, also set 0 (0x800>>6=32, mod 8 = 0)
    for a in set0_blocks + [intruder]:
        c.mem.write_word(a, a | 0xF000)

    # Fill both ways of set 0.
    c.read_word(0x000)  # way0
    c.read_word(0x400)  # way1
    # Third distinct tag → set full → round-robin evicts way0 (victim was 0).
    c.read_word(intruder)
    assert c._victim[0] == 1  # pointer advanced to 1

    # way0 (0x000) was evicted; reading it must miss and evict way1 next.
    before_miss = c.total_misses
    c.read_word(0x000)  # miss (evicted), fills way1, victim→0
    assert c.total_misses == before_miss + 1
    assert c._victim[0] == 0


@pytest.mark.parametrize("ways", [2, 4, 8, 16])
def test_n_way_cold_fills_invalid_first(mem, ways):
    """Cold misses fill invalid ways before any eviction; victim pointer stays 0."""
    c = make(ways * 64, 64, ways, mem)  # exactly 1 set, `ways` ways
    # The single set spans addresses 0 .. ways*64 with stride 64 between tags.
    base_tags = [i * 64 for i in range(ways)]
    for a in base_tags:
        c.mem.write_word(a, 0x1100 + a)

    for a in base_tags:
        c.read_word(a)  # each fills a distinct invalid way — no eviction

    # Victim pointer never advanced (no full-set eviction occurred).
    assert c._victim[0] == 0
    # All ways valid, all hits now.
    hits_before = c.total_hits
    for a in base_tags:
        c.read_word(a)
    assert c.total_hits == hits_before + ways


@pytest.mark.parametrize("ways", [4, 8])
def test_round_robin_cycles_through_all_ways(mem, ways):
    """Successive full-set evictions visit way 0,1,2,…,ways-1,0,… in order."""
    c = make(ways * 64, 64, ways, mem)  # 1 set
    # Prime: fill all ways.
    for i in range(ways):
        c.mem.write_word(i * 64, 0x1000 + i)
        c.read_word(i * 64)

    # Now evict `ways` more times; victim should cycle 0..ways-1 exactly once.
    victims = []
    for i in range(ways, 2 * ways):
        addr = i * 64
        c.mem.write_word(addr, 0x2000 + i)
        v_before = c._victim[0]
        c.read_word(addr)  # full-set miss
        victims.append(v_before)
    assert victims == list(range(ways))


# ── variable block size correctness ─────────────────────────────────────

@pytest.mark.parametrize("block", [16, 32, 64, 128])
def test_block_size_reads_correct_values(mem, block):
    """Aligned reads/writes return correct values at any block size, and no
    aligned access crosses a block boundary."""
    c = make(4 * 1024, block, 1, mem)
    # Write a known pattern across several blocks.
    for addr in range(0, block * 4, 4):
        c.mem.write_word(addr, (addr * 7 + 1) & 0xFFFFFFFF)

    for addr in range(0, block * 4, 4):
        expected = (addr * 7 + 1) & 0xFFFFFFFF
        assert c.read_word(addr) == expected


def test_smaller_block_more_conflict_misses(mem):
    """A 16 B block (4 words) fragments spatial locality: a streaming read of
    8 sequential words touches 2 blocks instead of 1, raising miss count
    vs the 64 B baseline. Sanity check on the accounting."""
    def miss_count(block):
        c = make(1024, block, 1, mem)
        for addr in range(0, 32, 4):  # 8 words = 32 bytes
            c.mem.write_word(addr, addr)
        for addr in range(0, 32, 4):
            c.read_word(addr)
        return c.total_misses

    assert miss_count(16) > miss_count(64)  # 2 blocks vs 1 block


# ── write-through / write-allocate still correct at ways>1 ──────────────

def test_write_through_allocate_at_n_way(mem):
    """A write miss allocates the block (write-allocate) and writes through to
    memory; a subsequent read of the same address hits."""
    c = make(1024, 64, 2, mem)
    c.write_word(0x40, 0xDEADBEEF)
    # Write-through: memory has the value.
    assert c.mem.read_word(0x40) == 0xDEADBEEF
    # Write-allocate: block resident, so a read hits.
    before = c.total_hits
    assert c.read_word(0x40) == 0xDEADBEEF
    assert c.total_hits == before + 1


# ── flush across sets × ways ────────────────────────────────────────────

def test_flush_invalidates_all_sets_and_ways(mem):
    c = make(1024, 64, 4, mem)  # 4 sets × 4 ways
    for a in (0x000, 0x040, 0x080, 0x0C0):
        c.mem.write_word(a, 0xAA)
        c.read_word(a)
    assert any(line.valid for s in c.sets for line in s)

    c.flush()
    assert all(not line.valid for s in c.sets for line in s)
    assert all(v == 0 for v in c._victim)
    assert c.total_accesses == 0
    assert c.last_access is None


# LRU replacement-policy cases.

def tags_in_set0(n, stride=0x400):
    """`n` distinct addresses all mapping to set 0, at the given address stride.

    Default stride 0x400 (= 1 KB) keeps them in set 0 for any of the small
    geometries used below (set index = (addr >> 6) & (num_sets-1), and these
    addresses are multiples of 0x400 = 2^10, so the low set bits stay 0).
    """
    return [i * stride for i in range(n)]


def tag_of(c, addr):
    """The cache tag for an address (uses the cache's own address split)."""
    return c.parse_address(addr)[0]


def test_lru_evicts_least_recently_used(mem):
    """2-way LRU: fill A + B, re-access A (promoting it to MRU), insert C →
    the least-recently-used B is evicted, not A. The canonical LRU test."""
    c = make(1024, 64, 2, mem, policy="lru")  # 8 sets, 2 ways
    a, b, intruder = tags_in_set0(3)
    for addr in (a, b, intruder):
        c.mem.write_word(addr, addr | 0xF000)

    c.read_word(a)          # miss → fill way0, age[0]=[0]
    c.read_word(b)          # miss → fill way1, age[0]=[0,1]
    c.read_word(a)          # HIT → promote A to MRU, age[0]=[1,0]
    c.read_word(intruder)   # miss, set full → evict age==0 (B on way1)

    # A must still be resident (way0); B (way1) was evicted for the intruder.
    assert c.find_way(0, tag_of(c, a)) == 0
    assert c.find_way(0, tag_of(c, intruder)) == 1
    # Reading B again must MISS — it was the LRU victim.
    before_miss = c.total_misses
    c.read_word(b)
    assert c.total_misses == before_miss + 1


def test_lru_worked_trace_n4_abcd_ae(mem):
    """Exercise a complete 4-way LRU replacement trace.

    Access stream A B C D A E @ N=4, single set. The expected state is:
        W0=A(2), W1=E(3)=MRU, W2=C(0)=LRU, W3=D(1),  B evicted.
    This pins down all three update rules (A cold-fill, C hit, B evict).
    """
    c = make(4 * 64, 64, 4, mem, policy="lru")  # exactly 1 set, 4 ways
    a, b, cc, d, e = tags_in_set0(5)
    for addr in (a, b, cc, d, e):
        c.mem.write_word(addr, addr | 0xF000)

    c.read_word(a)   # cold: A(0)
    c.read_word(b)   # cold: B(1)
    c.read_word(cc)  # cold: C(2)
    c.read_word(d)   # cold: D(3)
    c.read_word(a)   # hit W0 X=0 → A(3); B,C,D → 0,1,2
    c.read_word(e)   # full-set miss → evict age==0 (B on W1); insert E=3; rest -1

    # Exact per-way age and tags from the plan's table.
    assert c._age[0] == [2, 3, 0, 1]
    assert [c.sets[0][w].tag for w in range(4)] == [
        tag_of(c, a), tag_of(c, e), tag_of(c, cc), tag_of(c, d),
    ]
    # B evicted.
    assert c.find_way(0, tag_of(c, b)) == -1


def test_lru_recency_updates_on_read_hit(mem):
    """A read hit promotes the hit line's recency (Rule C). Uses a single-set
    4-way cache so the index/tag arithmetic is unambiguous; fills 3 of 4 ways
    (set not yet full)."""
    c = make(4 * 64, 64, 4, mem, policy="lru")  # 1 set, 4 ways
    a, b, cc, _d = tags_in_set0(4)
    for addr in (a, b, cc):
        c.mem.write_word(addr, addr | 0xF000)

    c.read_word(a)   # cold → age[0] = [0]
    c.read_word(b)   # cold → age[0] = [0, 1]
    c.read_word(cc)  # cold → age[0] = [0, 1, 2]
    # HIT on A (way0, old counter x=0): A promoted to MRU among the 3 valid
    # lines (counter = valid_count-1 = 2); B and C both had counters > 0 so
    # they each slide down by 1 → [2, 0, 1, 0]. Way3 is still invalid.
    c.read_word(a)
    assert c._age[0] == [2, 0, 1, 0]


def test_lru_recency_updates_on_write(mem):
    """A write_word to a resident line is a hit and updates recency (covers
    the write path + write-allocate under LRU)."""
    c = make(4 * 64, 64, 4, mem, policy="lru")  # 1 set, 4 ways
    a, b, cc, _d = tags_in_set0(4)
    for addr in (a, b, cc):
        c.mem.write_word(addr, 0)

    c.read_word(a)   # [0]
    c.read_word(b)   # [0,1]
    c.read_word(cc)  # [0,1,2]
    # Write-hit on A (the current LRU) must promote A to MRU among the 3 valid
    # lines (counter 2); B and C slide down → [2, 0, 1, 0].
    c.write_word(a, 0xDEAD)
    assert c._age[0] == [2, 0, 1, 0]
    assert c.total_hits >= 1   # the write was a hit
    # Write-through sanity.
    assert c.mem.read_word(a) == 0xDEAD


def test_fifo_and_lru_diverge(mem):
    """Same access stream, different victim: LRU rewards the re-accessed line,
    FIFO/round-robin ignores it. The canonical policy contrast."""
    a, b, intruder = tags_in_set0(3)

    def run(policy):
        c = make(1024, 64, 2, mem, policy=policy)  # 8 sets, 2 ways
        for addr in (a, b, intruder):
            c.mem.write_word(addr, addr | 0xF000)
        c.read_word(a)
        c.read_word(b)
        c.read_word(a)         # A re-accessed
        c.read_word(intruder)  # full-set miss
        return c

    lru = run("lru")
    fifo = run("fifo")

    # LRU: A was re-accessed (MRU) so B (the LRU) was evicted.
    assert lru.find_way(0, tag_of(lru, a)) == 0          # A survived
    assert lru.find_way(0, tag_of(lru, b)) == -1         # B evicted
    # FIFO: round-robin pointer was 0 → first eviction is way0 (A).
    assert fifo.find_way(0, tag_of(fifo, a)) == -1       # A evicted
    assert fifo.find_way(0, tag_of(fifo, b)) == 1        # B survived


@pytest.mark.parametrize("ways", [2, 4, 8, 16])
def test_lru_full_set_is_permutation(mem, ways):
    """Invariant: whenever a set is FULL, its age counters are a permutation
    of {0, ..., ways-1}. Hammer one set with random distinct accesses; only
    assert once the set has filled (the invariant is about full sets — during
    cold fill valid lines hold the contiguous range {0..valid-1} instead).

    Uses a single-set cache (total_size = ways*block), so all addresses land
    in set 0 regardless of stride.
    """
    import random
    c = make(ways * 64, 64, ways, mem, policy="lru")  # 1 set
    # Many more tags than ways, all in set 0 (single set → every address is).
    tags = [i * 0x400 for i in range(ways * 5)]
    for t in tags:
        c.mem.write_word(t, t | 0xF000)

    rng = random.Random(1234)
    set_full = False
    for _ in range(500):
        c.read_word(rng.choice(tags))
        # The invariant holds only once all ways are valid (the set is full).
        set_full = all(line.valid for line in c.sets[0]) or set_full
        if set_full:
            assert sorted(c._age[0]) == list(range(ways))


@pytest.mark.parametrize("ways", [2, 4, 8, 16])
def test_lru_cold_fills_invalid_first(mem, ways):
    """Cold misses fill invalid ways before any eviction; valid lines hold the
    contiguous range {0..valid_count-1} (Rule A). LRU analog of the FIFO test."""
    c = make(ways * 64, 64, ways, mem, policy="lru")  # 1 set
    base_tags = [i * 64 for i in range(ways)]   # all in set 0
    for a in base_tags:
        c.mem.write_word(a, 0x1100 + a)

    for a in base_tags:
        c.read_word(a)   # each fills a distinct invalid way — no eviction

    # Valid lines hold {0,1,...,ways-1} (last cold fill set counter = ways-1).
    assert sorted(c._age[0]) == list(range(ways))
    # FIFO victim pointer untouched (no full-set eviction happened).
    assert c._victim[0] == 0
    # All ways now hit.
    hits_before = c.total_hits
    for a in base_tags:
        c.read_word(a)
    assert c.total_hits == hits_before + ways


def test_lru_at_1_way_matches_direct_mapped(mem):
    """At ways=1, LRU ≡ FIFO ≡ direct-mapped: there's only one line to choose,
    so policy has no observable effect. Same miss pattern either way."""
    a0 = 0x000
    a1 = 0x400   # same set as a0

    def run(policy):
        c = make(1024, 64, 1, mem, policy=policy)
        c.mem.write_word(a0, 0xAAAA0000)
        c.mem.write_word(a1, 0xBBBB0000)
        c.read_word(a0)   # miss
        c.read_word(a1)   # miss, evicts a0
        c.read_word(a0)   # miss again
        return c.total_misses

    assert run("lru") == run("fifo") == 3


def test_flush_resets_lru_state(mem):
    """After flush(), _age is zeroed and eviction works as if freshly built."""
    c = make(4 * 64, 64, 4, mem, policy="lru")  # 1 set, 4 ways
    for i in range(4):
        c.mem.write_word(i * 64, 0x1000 + i)
        c.read_word(i * 64)
    assert any(a != 0 for a in c._age[0])   # some recency recorded

    c.flush()
    assert all(age == 0 for row in c._age for age in row)
    assert all(not line.valid for s in c.sets for line in s)
    # Freshly evicting: re-filling the same set works as on a cold cache.
    c.read_word(0)
    assert c._age[0][0] == 0    # single valid line, counter 0 (Rule A)


def test_lru_rejects_bad_policy():
    """Unknown policy strings raise ValueError at construction."""
    with pytest.raises(ValueError):
        make(1024, 64, 2, policy="mru")
