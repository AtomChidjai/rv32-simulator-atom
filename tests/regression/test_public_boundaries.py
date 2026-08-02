"""Cache geometry and public API boundary regressions."""

import pytest

import rv32i
from rv32i.cache import Cache, CacheGeometry, DirectMappedCache
from rv32i.memory import Memory


# Cache geometry
@pytest.mark.parametrize("ways", [1, 2, 4, 8, 16])
def test_cache_accepts_all_documented_ways(ways):
    g = CacheGeometry.from_size(total_size=1 << 12, block_size=64, ways=ways)
    assert g.ways == ways


@pytest.mark.parametrize("bad_ways", [0, 3, 5, 6, 7, 9, 15, 17, 32])
def test_cache_rejects_undocumented_ways(bad_ways):
    """Only the documented associativity values are accepted."""
    with pytest.raises(ValueError, match="ways"):
        CacheGeometry.from_size(total_size=1 << 12, block_size=64, ways=bad_ways)


def test_cache_rejects_geometry_with_zero_tag_bits():
    """A geometry with no tag bits is invalid."""
    with pytest.raises(ValueError, match="tag"):
        CacheGeometry.from_size(total_size=1 << 32, block_size=64, ways=1)


# Compatibility alias
def test_direct_mapped_cache_alias_points_at_cache():
    """The compatibility alias continues to reference Cache."""
    assert DirectMappedCache is Cache


# Cache statistics
def test_cache_stats_with_no_accesses_returns_zero_rate_not_nan():
    """Empty statistics return a zero hit rate, not NaN."""
    c = Cache(Memory())
    s = c.get_stats()
    assert s["total_accesses"] == 0
    assert s["hit_rate"] == 0.0
    assert s["hit_rate"] == s["hit_rate"]


# Public package surface
def test_rv32i_public_surface_is_exactly_simulator():
    """The package root exports only the orchestrating ``Simulator`` class."""
    assert rv32i.__all__ == ["Simulator"]
    public = [n for n in dir(rv32i) if not n.startswith("_")]
    assert "Simulator" in public


# CSR interrupt boundary
def test_devices_update_mip_through_csr_api():
    from rv32i.csr import CSRFile
    from rv32i.devices import clear_external_irq, raise_external_irq

    csr = CSRFile()
    raise_external_irq(csr)
    assert csr.read(0x344) & (1 << 11)

    clear_external_irq(csr)
    assert not csr.read(0x344) & (1 << 11)


# Hit and miss accounting
def test_cache_hit_then_miss_accounting_is_consistent():
    """Total accesses equal hits plus misses."""
    mem = Memory()
    c = Cache(mem, total_size=1 << 10, block_size=64, ways=1)
    c.read_word(0x100)
    c.read_word(0x100)
    s = c.get_stats()
    assert s["total_accesses"] == s["total_hits"] + s["total_misses"]
    assert s["total_hits"] == 1
    assert s["total_misses"] == 1
