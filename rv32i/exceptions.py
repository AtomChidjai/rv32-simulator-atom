"""RISC-V trap exceptions and synchronous trap factories."""

class TrapException(Exception):
    def __init__(self, mcause: int, mtval: int = 0, description: str = ""):
        self.mcause = mcause
        self.mtval = mtval
        self.description = description
        super().__init__(description)

def illegal_instruction(inst: int, pc: int) -> TrapException:
    return TrapException(mcause=2, mtval=inst, description=f"Illegal instruction 0x{inst:08x} at 0x{pc:08x}")

def environment_call(mode: int = 3) -> TrapException:
    return TrapException(mcause=8+mode, mtval=0, description=f"Environment call from mode {mode}")

def load_address_misaligned(addr: int) -> TrapException:
    """Load from a misaligned address (mcause=4). mtval = faulting address."""
    return TrapException(mcause=4, mtval=addr, description=f"Load address misaligned: 0x{addr:08x}")

def store_address_misaligned(addr: int) -> TrapException:
    """Store to a misaligned address (mcause=6). mtval = faulting address."""
    return TrapException(mcause=6, mtval=addr, description=f"Store address misaligned: 0x{addr:08x}")

def instruction_address_misaligned(addr: int) -> TrapException:
    """Instruction fetch from a misaligned address (mcause=0). mtval = faulting address.

    Note: this core requires only 2-byte (halfword) instruction alignment (RVC),
    so this only fires for odd PC values, which should never occur in normal
    execution; it exists for completeness/spec-conformance.
    """
    return TrapException(mcause=0, mtval=addr, description=f"Instruction address misaligned: 0x{addr:08x}")
