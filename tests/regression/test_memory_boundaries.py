"""Memory address and chunk-boundary regressions."""

import pytest

from rv32i.memory import CHUNK_SIZE, Memory


# Chunk-spanning reads
def test_read_bytes_preserves_data_across_chunk_boundary():
    mem = Memory()
    for i in range(8):
        mem.write_byte(CHUNK_SIZE - 4 + i, 0x10 + i)

    assert mem.read_bytes(CHUNK_SIZE - 4, 8) == 0x1716151413121110


def test_device_read_still_bypasses_chunks_across_boundary(fresh_cache):
    """A registered MMIO callback remains authoritative across a boundary."""
    mem = fresh_cache.mem
    boundary = CHUNK_SIZE

    mem.register_device(
        "span", boundary - 4, 8,
        on_read=lambda addr, size: 0xDEADBEEFCAFE,
        on_write=lambda addr, val, size: None,
    )

    assert mem.read_bytes(boundary - 4, 8) == 0xDEADBEEFCAFE


# Address-space boundaries
def test_read_halfword_at_end_of_address_space_is_valid():
    """The final in-range halfword is accepted by the explicit range guard."""
    mem = Memory()
    top = 0xFFFFFFFE
    mem.write_byte(top, 0xAA)
    mem.write_byte(top + 1, 0xBB)
    assert mem.read_halfword(top) == 0xBBAA


def test_read_byte_negative_address_raises():
    mem = Memory()
    with pytest.raises(IndexError):
        mem.write_byte(-1, 0x41)
    with pytest.raises(IndexError):
        mem.read_byte(-1)


def test_fetch_and_read_reject_addresses_outside_rv32():
    mem = Memory()
    addr = 0x1_0000_0000 + 4
    with pytest.raises(IndexError):
        mem.fetch_instruction(addr)
    with pytest.raises(IndexError):
        mem.read_byte(addr)


def test_fetch_instruction_preserves_upper_half_across_chunk_boundary():
    mem = Memory()
    address = CHUNK_SIZE - 2
    mem.load_bytes(address, b"\x13\x00\xf0\x0f")

    assert mem.fetch_instruction(address) == (0x0FF00013, 4)


def test_read_word_within_a_chunk_is_correct():
    """Ordinary intra-chunk reads remain correct."""
    mem = Memory()
    mem.write_word(0x100, 0xDEADBEEF)
    assert mem.read_word(0x100) == 0xDEADBEEF
    mem.write_word(CHUNK_SIZE - 4, 0xCAFEBABE)
    assert mem.read_word(CHUNK_SIZE - 4) == 0xCAFEBABE
