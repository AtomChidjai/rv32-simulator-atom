"""Shared fixtures for boundary regression tests."""

import pytest


@pytest.fixture
def fresh_memory():
    """A brand-new, never-shared ``Memory`` (no chunks, no devices)."""
    from rv32i.memory import Memory

    return Memory()


@pytest.fixture
def fresh_cache(fresh_memory):
    """A tiny direct-mapped cache over a fresh memory."""
    from rv32i.cache import Cache

    return Cache(fresh_memory, total_size=1 << 12, block_size=64, ways=1)
