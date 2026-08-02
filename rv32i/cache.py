"""Configurable split-L1 cache with FIFO and LRU replacement."""

from dataclasses import dataclass

from .memory import Memory

BLOCK_SIZE = 64
NUM_LINES = 512
WORD_BYTES = 4
WORDS_PER_BLOCK = BLOCK_SIZE // WORD_BYTES
OFFSET_BITS = 6
INDEX_BITS = 9
TAG_BITS = 17

BYTE_OFFSET_MASK = 0x3
WORD_OFFSET_SHIFT = 2
WORD_OFFSET_MASK = 0xF
INDEX_SHIFT = 6
INDEX_MASK = 0x1FF
TAG_SHIFT = 17

def is_pow2(n: int) -> bool:
    """Return True if n is a power of two."""
    return n > 0 and (n & (n - 1)) == 0


def log2_pow2(n: int) -> int:
    """Find the number of bit that represent n from is_pow2(n)."""
    assert is_pow2(n), f"{n} is not a power of two"
    return n.bit_length() - 1


@dataclass(frozen=True)
class CacheGeometry:
    """Immutable layout derived from total size, block size, and ways."""

    total_size: int
    block_size: int
    ways: int
    num_lines: int
    num_sets: int
    words_per_block: int
    offset_bits: int
    word_offset_bits: int
    index_bits: int
    tag_bits: int
    byte_offset_mask: int
    word_offset_shift: int
    word_offset_mask: int
    index_shift: int
    index_mask: int
    tag_shift: int

    @classmethod
    def from_size(cls, total_size: int, block_size: int, ways: int) -> "CacheGeometry":
        if not is_pow2(block_size) or block_size < WORD_BYTES:
            raise ValueError(f"block_size must be a power of two >= {WORD_BYTES}, got {block_size}")
        if ways not in (1, 2, 4, 8, 16):
            raise ValueError(f"ways must be one of 1/2/4/8/16, got {ways}")
        if not is_pow2(total_size) or total_size < block_size:
            raise ValueError(f"total_size must be a power of two >= block_size, got {total_size}")
        if total_size % (block_size * ways) != 0:
            raise ValueError(
                f"total_size {total_size} not divisible by block_size*ways "
                f"({block_size}*{ways})"
            )

        num_lines = total_size // block_size
        num_sets = num_lines // ways
        if not is_pow2(num_sets) or num_sets < 1:
            raise ValueError(f"num_sets must be a power of two >= 1, got {num_sets}")

        offset_bits = log2_pow2(block_size)
        word_offset_bits = offset_bits - 2
        index_bits = log2_pow2(num_sets)
        tag_bits = 32 - offset_bits - index_bits
        if tag_bits < 1:
            raise ValueError(
                f"geometry leaves no tag bits (tag_bits={tag_bits}); "
                f"cache too large"
            )

        return cls(
            total_size=total_size,
            block_size=block_size,
            ways=ways,
            num_lines=num_lines,
            num_sets=num_sets,
            words_per_block=block_size // WORD_BYTES,
            offset_bits=offset_bits,
            word_offset_bits=word_offset_bits,
            index_bits=index_bits,
            tag_bits=tag_bits,
            byte_offset_mask=(1 << 2) - 1,
            word_offset_shift=2,
            word_offset_mask=(1 << word_offset_bits) - 1,
            index_shift=offset_bits,
            index_mask=(1 << index_bits) - 1 if index_bits > 0 else 0,
            tag_shift=offset_bits + index_bits,
        )


class CacheLine:
    __slots__ = ("valid", "tag", "data")

    def __init__(self, block_size: int = BLOCK_SIZE):
        self.valid = False
        self.tag = 0
        self.data = bytearray(block_size)


class CacheAccess:
    """The last access recorded for the GUI cache panel."""

    __slots__ = ("address", "tag", "index", "word_offset", "byte_offset", "hit", "way")

    def __init__(self, address, tag, index, word_offset, byte_offset, hit, way=-1):
        self.address = address
        self.tag = tag
        self.index = index
        self.word_offset = word_offset
        self.byte_offset = byte_offset
        self.hit = hit
        self.way = way


class Cache:
    """One configurable L1 instruction or data cache."""

    def __init__(
        self,
        memory: Memory,
        total_size: int = 32 * 1024,
        block_size: int = BLOCK_SIZE,
        ways: int = 1,
        policy: str = "fifo",
    ):
        if policy not in ("fifo", "lru"):
            raise ValueError(f"policy must be 'fifo' or 'lru', got {policy!r}")
        self.geom = CacheGeometry.from_size(total_size, block_size, ways)
        self.mem = memory
        self.policy = policy

        bs = self.geom.block_size
        self.sets: list[list[CacheLine]] = [[CacheLine(bs) for _ in range(ways)] for _ in range(self.geom.num_sets)]
        self._victim: list[int] = [0] * self.geom.num_sets

        self._max_age = self.geom.ways - 1
        self._age: list[list[int]] = [[0] * self.geom.ways for _ in range(self.geom.num_sets)]

        self.total_accesses = 0
        self.total_hits = 0
        self.total_misses = 0
        self.last_access: CacheAccess | None = None

    @property
    def num_sets(self) -> int:
        return self.geom.num_sets

    @property
    def num_lines(self) -> int:
        return self.geom.num_lines

    @property
    def ways(self) -> int:
        return self.geom.ways

    @property
    def block_size(self) -> int:
        return self.geom.block_size

    @property
    def words_per_block(self) -> int:
        return self.geom.words_per_block

    @property
    def index_bits(self) -> int:
        return self.geom.index_bits

    @property
    def tag_bits(self) -> int:
        return self.geom.tag_bits

    @property
    def offset_bits(self) -> int:
        return self.geom.offset_bits

    @property
    def index_shift(self) -> int:
        return self.geom.index_shift

    @property
    def index_mask(self) -> int:
        return self.geom.index_mask

    @property
    def tag_shift(self) -> int:
        return self.geom.tag_shift

    def set_index_of(self, addr: int) -> int:
        """Set index that a byte address maps to (used by GUI lookup)."""
        return (addr >> self.geom.index_shift) & self.geom.index_mask

    @property
    def lines(self) -> list[CacheLine]:
        """Return the backward-compatible flat set/way view."""
        return [line for s in self.sets for line in s]

    def parse_address(self, addr):
        g = self.geom
        byte_offset = addr & g.byte_offset_mask
        word_offset = (addr >> g.word_offset_shift) & g.word_offset_mask
        index = (addr >> g.index_shift) & g.index_mask
        tag = addr >> g.tag_shift
        block_addr = addr & ~(g.block_size - 1)
        return tag, index, word_offset, byte_offset, block_addr

    def find_way(self, set_idx, tag):
        """Return the way holding (set_idx, tag), or -1 if absent."""
        for w, line in enumerate(self.sets[set_idx]):
            if line.valid and line.tag == tag:
                return w
        return -1

    def on_hit(self, set_idx, way):
        """Promote an LRU hit to the newest valid age."""
        if self.policy != "lru":
            return
        ages = self._age[set_idx]
        x = ages[way]
        valid = sum(1 for l in self.sets[set_idx] if l.valid)
        ages[way] = valid - 1
        for w in range(self.geom.ways):
            if w != way and ages[w] > x:
                ages[w] -= 1

    def victim_way(self, set_idx):
        """Choose an invalid way, LRU age zero, or the FIFO pointer."""
        for w, line in enumerate(self.sets[set_idx]):
            if not line.valid:
                if self.policy == "lru":
                    self._age[set_idx][w] = sum(
                        1 for l in self.sets[set_idx] if l.valid
                    )
                return w

        if self.policy == "lru":
            ages = self._age[set_idx]
            way = next(w for w in range(self.geom.ways) if ages[w] == 0)
            ages[way] = self._max_age
            for w in range(self.geom.ways):
                if w != way:
                    ages[w] -= 1
            return way

        v = self._victim[set_idx]
        self._victim[set_idx] = (v + 1) % self.geom.ways
        return v

    def load_block(self, set_idx, way, tag, block_addr):
        line = self.sets[set_idx][way]
        has_device = False
        for i in range(self.geom.block_size):
            addr = block_addr + i
            if self.is_device(addr):
                line.data[i] = 0
                has_device = True
            else:
                line.data[i] = self.mem.read_byte(addr, signed=False)
        line.valid = not has_device
        line.tag = tag

    def check_alignment(self, addr, size, cause="load"):
        """Raise the architectural trap for a misaligned access."""
        if addr % size != 0:
            from .exceptions import (
                load_address_misaligned,
                store_address_misaligned,
                instruction_address_misaligned,
            )
            if cause == "store":
                raise store_address_misaligned(addr)
            if cause == "fetch":
                raise instruction_address_misaligned(addr)
            raise load_address_misaligned(addr)

    def is_device(self, addr):
        return self.mem.find_device(addr) is not None

    def record(self, addr, tag, set_idx, word_offset, byte_offset, hit, way=-1):
        self.total_accesses += 1
        if hit:
            self.total_hits += 1
        else:
            self.total_misses += 1
        self.last_access = CacheAccess(addr, tag, set_idx, word_offset, byte_offset, hit, way)

    def read_cached(self, set_idx, way, word_offset, byte_offset, size):
        line = self.sets[set_idx][way]
        base = word_offset * WORD_BYTES + byte_offset
        raw = line.data[base : base + size]
        return int.from_bytes(raw, byteorder="little")

    def write_cached(self, set_idx, way, word_offset, byte_offset, val, size):
        line = self.sets[set_idx][way]
        base = word_offset * WORD_BYTES + byte_offset
        line.data[base : base + size] = val.to_bytes(size, byteorder="little")

    def sign_extend(self, val, bits):
        sign_bit = 1 << (bits - 1)
        return (val ^ sign_bit) - sign_bit

    def read(self, address, size, bits, signed):
        self.check_alignment(address, size, cause="load")
        tag, set_idx, word_offset, byte_offset, block_addr = self.parse_address(address)

        if self.is_device(address):
            val = self.mem.read_bytes(address, size)
            self.record(address, tag, set_idx, word_offset, byte_offset, False)
            return self.sign_extend(val, bits) if signed else val

        way = self.find_way(set_idx, tag)
        if way >= 0:
            self.on_hit(set_idx, way)
            self.record(address, tag, set_idx, word_offset, byte_offset, True, way)
        else:
            way = self.victim_way(set_idx)
            self.load_block(set_idx, way, tag, block_addr)
            self.record(address, tag, set_idx, word_offset, byte_offset, False, way)

        val = self.read_cached(set_idx, way, word_offset, byte_offset, size)
        return self.sign_extend(val, bits) if signed else val

    def read_byte(self, address, signed=False):
        return self.read(address, 1, 8, signed)

    def read_halfword(self, address, signed=False):
        return self.read(address, 2, 16, signed)

    def read_word(self, address):
        return self.read(address, 4, 32, False)

    def write(self, address, val, size, mask):
        self.check_alignment(address, size, cause="store")
        tag, set_idx, word_offset, byte_offset, block_addr = self.parse_address(address)
        val &= mask

        if self.is_device(address):
            self.mem.write_bytes(address, val, size)
            self.record(address, tag, set_idx, word_offset, byte_offset, False)
            return

        way = self.find_way(set_idx, tag)
        hit = way >= 0
        if hit:
            self.on_hit(set_idx, way)
        else:
            way = self.victim_way(set_idx)
            self.load_block(set_idx, way, tag, block_addr)

        self.write_cached(set_idx, way, word_offset, byte_offset, val, size)
        self.mem.write_bytes(address, val, size)
        self.record(address, tag, set_idx, word_offset, byte_offset, hit, way)

    def write_byte(self, address, val):
        self.write(address, val, 1, 0xFF)

    def write_halfword(self, address, val):
        self.write(address, val, 2, 0xFFFF)

    def write_word(self, address, val):
        self.write(address, val, 4, 0xFFFFFFFF)

    def fetch_instruction(self, pc: int) -> tuple[int, int]:
        addr = pc & 0xFFFFFFFF
        self.check_alignment(addr, 2, cause="fetch")

        half = self.read_halfword(addr, signed=False)
        if (half & 0x3) == 0x3:
            upper = self.read_line_byte(addr + 2, 2)
            return ((upper << 16) | half, 4)
        return (half, 2)

    def read_line_byte(self, addr: int, size: int) -> int:
        """Read a resident upper halfword without recording a second access."""
        tag, set_idx, word_offset, byte_offset, _ = self.parse_address(addr)
        way = self.find_way(set_idx, tag)
        if way < 0:
            return self.read_halfword(addr, signed=False)
        base = word_offset * WORD_BYTES + byte_offset
        return int.from_bytes(
            self.sets[set_idx][way].data[base : base + size], byteorder="little"
        )

    def get_stats(self):
        rate = (self.total_hits / self.total_accesses * 100) if self.total_accesses else 0.0
        return {
            "total_accesses": self.total_accesses,
            "total_hits": self.total_hits,
            "total_misses": self.total_misses,
            "hit_rate": rate,
        }

    def flush(self):
        for s in self.sets:
            for line in s:
                line.valid = False
                line.tag = 0
                line.data = bytearray(self.geom.block_size)
        self._victim = [0] * self.geom.num_sets
        self._age = [[0] * self.geom.ways for _ in range(self.geom.num_sets)]
        self.total_accesses = 0
        self.total_hits = 0
        self.total_misses = 0
        self.last_access = None


DirectMappedCache = Cache
