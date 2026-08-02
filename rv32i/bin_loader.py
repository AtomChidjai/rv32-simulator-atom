"""Load flat binary images into simulator memory."""

from .memory import Memory

def load_bin(memory: Memory, filepath: str, base_address: int = 0) -> int:
    with open(filepath, "rb") as f:
        data = f.read()

    if base_address + len(data) > memory.size:
        raise ValueError(
            f"binary ({len(data)} bytes) exceeds memory size"
            f"({memory.size} bytes) starting at 0x{base_address:08x}"
        )

    memory.load_bytes(base_address, data)
    return len(data)
