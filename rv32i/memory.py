"""Sparse 4 GB backing store and MMIO bus."""

from .constants import WORD_BYTES, WORD_MASK

CHUNK_ORDER     = 16
CHUNK_SIZE      = 1 << CHUNK_ORDER
CHUNK_MASK      = CHUNK_SIZE - 1
ADDRESS_SPACE   = 1 << 32

class Memory:
    def __init__(self) -> None:
        self.chunks: dict[int, bytearray] = {}
        self._size = ADDRESS_SPACE
        self._devices: list[dict] = []
        self._waiting_for_input = False

    @property
    def size(self) -> int:
        return self._size

    @property
    def waiting_for_input(self) -> bool:
        return self._waiting_for_input

    def wait_for_input(self) -> None:
        self._waiting_for_input = True

    def resume_input(self) -> None:
        self._waiting_for_input = False

    def reset(self) -> None:
        """Drop all chunks and registered devices — back to an empty 4 GB space."""
        self.chunks.clear()
        self._devices.clear()
        self.resume_input()

    def snapshot_chunks(self) -> dict[int, bytes]:
        """Return a detached copy of allocated backing-memory chunks."""
        return {idx: bytes(chunk) for idx, chunk in self.chunks.items()}

    def restore_chunks(self, snapshot: dict[int, bytes]) -> None:
        """Replace backing memory from a snapshot while preserving MMIO mappings."""
        restored: dict[int, bytearray] = {}
        max_chunk = ADDRESS_SPACE // CHUNK_SIZE
        for idx, data in snapshot.items():
            if not 0 <= idx < max_chunk:
                raise ValueError(f"chunk index outside memory: {idx}")
            if len(data) != CHUNK_SIZE:
                raise ValueError(
                    f"chunk {idx} has {len(data)} bytes; expected {CHUNK_SIZE}"
                )
            restored[idx] = bytearray(data)
        self.chunks = restored

    def register_device(self, name: str, base: int, size: int, on_read, on_write) -> None:
        """Register a non-overlapping MMIO range."""
        for d in self._devices:
            if base < d["base"] + d["size"] and base + size > d["base"]:
                raise ValueError(f"device '{name}' overlaps '{d['name']}'")
        self._devices.append({"name": name, "base": base, "size": size, "on_read": on_read, "on_write": on_write})

    def find_device(self, addr: int) -> dict | None:
        """Return the device (dict) whose range covers ``addr``, or None."""
        for d in self._devices:
            if d["base"] <= addr < d["base"] + d["size"]:
                return d
        return None

    @staticmethod
    def chunk_idx(addr: int) -> int:
        return addr >> CHUNK_ORDER

    @staticmethod
    def chunk_offset(addr: int) -> int:
        return addr & CHUNK_MASK

    def get_chunk(self, addr: int, create: bool = True) -> bytearray | None:
        idx = self.chunk_idx(addr)
        chunk = self.chunks.get(idx)
        if chunk is None and create:
            chunk = bytearray(CHUNK_SIZE)
            self.chunks[idx] = chunk
        return chunk

    @staticmethod
    def sign_extend(val: int, bits: int) -> int:
        sign_bit = 1 << (bits - 1)
        return (val ^ sign_bit) - sign_bit

    @staticmethod
    def check_alignment(address: int, alignment: int, cause: str = "load") -> None:
        """Raise the architectural trap for a misaligned access."""
        if address % alignment != 0:
            from .exceptions import (
                load_address_misaligned,
                store_address_misaligned,
                instruction_address_misaligned,
            )
            if cause == "store":
                raise store_address_misaligned(address)
            if cause == "fetch":
                raise instruction_address_misaligned(address)
            raise load_address_misaligned(address)

    def check_range(self, address: int, length: int) -> None:
        if address < 0:
            raise IndexError(f"address must be positive, got {address}")
        if length < 0:
            raise ValueError(f"length must be positive, got {length}")
        if address + length > self._size:
            raise IndexError("access outside memory bound (32-bit space)")

    def load_bytes(self, address: int, val: bytes | bytearray | list[int] | tuple[int, ...]) -> None:
        val = bytes(val)
        end = len(val)
        self.check_range(address, end)
        offset = 0
        while offset < end:
            addr = address + offset
            chunk = self.get_chunk(addr, create=True)
            off = self.chunk_offset(addr)
            space = CHUNK_SIZE - off
            take = min(space, end - offset)
            chunk[off : off + take] = val[offset : offset + take]
            offset += take

    def read(self, address: int, size: int, signed: bool) -> int:
        self.check_range(address, size)
        if size == 0:
            return 0
        dev = self.find_device(address)
        if dev is not None:
            val = dev["on_read"](address, size) or 0
            return self.sign_extend(val, size * 8) if signed else val

        val = self.read_backing(address, size)
        return self.sign_extend(val, size * 8) if signed else val

    def read_backing(self, address: int, size: int) -> int:
        """Read little-endian bytes across sparse chunk boundaries."""
        value = 0
        offset = 0
        while offset < size:
            addr = address + offset
            chunk = self.get_chunk(addr, create=False)
            chunk_offset = self.chunk_offset(addr)
            take = min(CHUNK_SIZE - chunk_offset, size - offset)
            if chunk is not None:
                part = int.from_bytes(
                    chunk[chunk_offset : chunk_offset + take],
                    byteorder="little",
                )
                value |= part << (offset * 8)
            offset += take
        return value

    def read_byte(self, address: int, signed: bool = False) -> int:
        return self.read(address, 1, signed)

    def peek_byte(self, address: int) -> int:
        """Read backing memory without invoking MMIO callbacks."""
        self.check_range(address, 1)
        if self.find_device(address) is not None:
            return 0
        chunk = self.get_chunk(address, create=False)
        return 0 if chunk is None else chunk[self.chunk_offset(address)]

    def read_halfword(self, address: int, signed: bool = False) -> int:
        self.check_alignment(address, 2, cause="load")
        return self.read(address, 2, signed)

    def read_word(self, address: int) -> int:
        self.check_alignment(address, WORD_BYTES, cause="load")
        return self.read(address, WORD_BYTES, False)

    def read_bytes(self, address: int, size: int) -> int:
        return self.read(address, size, False)

    def write_byte(self, address: int, val: int) -> None:
        self.check_range(address, 1)
        dev = self.find_device(address)
        if dev is not None:
            dev["on_write"](address, val & 0xFF, 1)
            return
        chunk = self.get_chunk(address, create=True)
        off = self.chunk_offset(address)
        chunk[off] = val & 0xFF

    def write(self, address: int, val: int, size: int, mask: int) -> None:
        self.check_alignment(address, size, cause="store")
        self.check_range(address, size)
        val &= mask
        dev = self.find_device(address)
        if dev is not None:
            dev["on_write"](address, val, size)
            return
        chunk = self.get_chunk(address, create=True)
        off = self.chunk_offset(address)
        chunk[off : off + size] = val.to_bytes(size, byteorder="little")

    def write_halfword(self, address: int, val: int) -> None:
        self.write(address, val, 2, 0xFFFF)

    def write_word(self, address: int, val: int) -> None:
        self.write(address, val, WORD_BYTES, WORD_MASK)

    def write_bytes(self, address: int, val: int, size: int) -> None:
        self.write(address, val, size, (1 << (size * 8)) - 1)

    def fetch_halfword(self, addr: int) -> int:
        self.check_range(addr, 2)
        self.check_alignment(addr, 2, cause="fetch")
        return self.read_backing(addr, 2)

    def fetch_instruction(self, pc: int) -> tuple[int, int]:
        addr = pc
        self.check_range(addr, 2)
        self.check_alignment(addr, 2, cause="fetch")
        half = self.fetch_halfword(addr)
        if (half & 0x3) == 0x3:
            self.check_range(addr, 4)
            return self.read_backing(addr, 4), 4
        else:
            return half, 2

    def description(self, address: int = 0, length: int = 256) -> str:
        stop = min(address + length, ADDRESS_SPACE)
        n = len(self.chunks)
        lines = [f"Memory: 32-bit ({n} chunk{'s' if n != 1 else ''} × {CHUNK_SIZE // 1024} KB) (chunk index: {self.chunk_idx(address)})"]

        addr = address
        while addr < stop:
            chunk = self.get_chunk(addr, create=False)
            off = self.chunk_offset(addr)
            span = min(CHUNK_SIZE - off, stop - addr)

            for r_off in range(0, span, 16):
                take = min(16, span - r_off)
                row = bytes(chunk[off + r_off : off + r_off + take]) if chunk else b"\x00" * take
                hx = " ".join(f"{b:02x}" for b in row)
                asc = "".join(chr(b) if 32 <= b < 127 else "." for b in row)
                lines.append(f"  0x{addr + r_off:08x}  {hx:<48}  {asc}")
                
            addr += span
            
        return "\n".join(lines)
