"""Machine-mode CSRs, counters, traps, and interrupts."""

from .constants import CSR_ADDR, INTERRUPT_PRIORITY

_CAUSE_NAMES = {
    0x00000000: "Instruction Address Misaligned",
    0x00000002: "Illegal Instruction",
    0x00000003: "Breakpoint",
    0x00000004: "Load Address Misaligned",
    0x00000006: "Store/AMO Address Misaligned",
    0x0000000B: "Env Call (M-mode)",
    0x80000003: "MSI (Software)",
    0x80000007: "MTI (Timer)",
    0x8000000B: "MEI (External)",
}

_READ_ONLY_CSR_ADDRS = frozenset({0x301})


class CSRFile:
    def __init__(self) -> None:
        self._csr = {}
        self._csr[0x300] = 0x00001800  # mstatus: MPP=3 (M-mode)
        self._csr[0x301] = 0x40001104  # misa: MXL=1 (RV32) | I(bit8) | M(bit12) | C(bit2)
        self._csr[0x304] = 0x00000000  # mie (all disabled)
        self._csr[0x305] = 0x00000000  # mtvec
        self._csr[0x340] = 0x00000000  # mscratch
        self._csr[0x341] = 0x00000000  # mepc
        self._csr[0x342] = 0x00000000  # mcause
        self._csr[0x343] = 0x00000000  # mtval
        self._csr[0x344] = 0x00000000  # mip
        self._csr[0xB00] = 0x00000000  # mcycle
        self._csr[0xB02] = 0x00000000  # minstret
        self.trap_log: list[dict] = []

    def read(self, addr: int) -> int:
        if addr not in self._csr:
            return 0
        return self._csr[addr] & 0xFFFFFFFF

    def is_implemented(self, addr: int) -> bool:
        """Return whether ``addr`` belongs to the simulator's CSR set."""
        return addr in self._csr

    def is_writable(self, addr: int) -> bool:
        """Return whether ``addr`` is implemented and accepts writes."""
        return self.is_implemented(addr) and addr not in _READ_ONLY_CSR_ADDRS

    def snapshot(self) -> dict[int, int]:
        """Return a detached copy of all implemented CSR values."""
        return {addr: value & 0xFFFFFFFF for addr, value in self._csr.items()}

    def set_interrupt_pending(self, bit: int, pending: bool) -> None:
        """Set or clear one machine-interrupt pending bit in ``mip``."""
        if not 0 <= bit < 32:
            raise ValueError(f"interrupt bit must be in range 0..31, got {bit}")
        mask = 1 << bit
        mip = self.read(0x344)
        self.write(0x344, (mip | mask) if pending else (mip & ~mask))

    def reset(self) -> None:
        """Restore the reset values of every implemented CSR."""
        self._csr[0x300] = 0x00001800  # mstatus: MPP=3 (M-mode)
        self._csr[0x301] = 0x40001104  # misa: MXL=1 (RV32) | I(bit8) | M(bit12) | C(bit2)
        self._csr[0x304] = 0x00000000  # mie (all disabled)
        self._csr[0x305] = 0x00000000  # mtvec
        self._csr[0x340] = 0x00000000  # mscratch
        self._csr[0x341] = 0x00000000  # mepc
        self._csr[0x342] = 0x00000000  # mcause
        self._csr[0x343] = 0x00000000  # mtval
        self._csr[0x344] = 0x00000000  # mip
        self._csr[0xB00] = 0x00000000  # mcycle
        self._csr[0xB02] = 0x00000000  # minstret
        self.trap_log.clear()


    def write(self, addr: int, val: int) -> None:
        if not self.is_writable(addr):
            return
        self._csr[addr] = val & 0xFFFFFFFF

    def increment_cycle(self) -> None:
        self._csr[0xB00] = (self._csr.get(0xB00, 0) + 1) & 0xFFFFFFFF

    def increment_instret(self) -> None:
        self._csr[0xB02] = (self._csr.get(0xB02, 0) + 1) & 0xFFFFFFFF

    def trap_enter(
        self,
        proc,
        mcause: int,
        mtval: int = 0,
        mepc: int | None = None,
    ) -> None:
        """Enter a trap: save mepc/mcause/mtval, update mstatus (MPIE/MIE/MPP),
        and jump to mtvec. If mtvec is 0 (not set) the machine HALTs instead.
        Appends a structured entry to ``trap_log``."""
        if mepc is None:
            mepc = proc.read_pc()
        self.write(0x341, mepc)
        self.write(0x342, mcause & 0xFFFFFFFF)
        self.write(0x343, mtval & 0xFFFFFFFF)

        mstatus = self.read(0x300)
        mie = (mstatus >> 3) & 1
        if mie:
            mstatus |= (1 << 7)
        else:
            mstatus &= ~(1 << 7)
        mstatus &= ~(1 << 3)
        mstatus |= (3 << 11)
        self.write(0x300, mstatus)

        mtvec = self.read(0x305)
        base = mtvec & ~0x3
        cause_name = _CAUSE_NAMES.get(mcause, f"Unknown (0x{mcause:08x})")
        is_interrupt = (mcause >> 31) & 1
        kind = "INT" if is_interrupt else "EXC"

        entry = {
            "cycle": self._csr.get(0xB00, 0),
            "kind": kind,
            "cause": mcause,
            "cause_name": cause_name,
            "mepc": mepc,
            "mtval": mtval,
            "mtvec": base,
            "halted": base == 0,
            "priority": INTERRUPT_PRIORITY.index(mcause & 0x7FFFFFFF) if is_interrupt and (mcause & 0x7FFFFFFF) in INTERRUPT_PRIORITY else -1,
        }
        self.trap_log.append(entry)

        if base == 0:
            proc.halt()
            return
        proc.set_pc(base)

    def check_pending_trap(self, proc, pc: int = None, before_exec: bool = False, inst_size: int = 4) -> bool:
        """If a machine interrupt is enabled-and-pending, take it now.

        ``before_exec=True`` means we are between instructions (mepc = the
        about-to-run pc); otherwise we set mepc = pc + inst_size (after-run).
        Priority order is ``INTERRUPT_PRIORITY`` (MEI > MSI > MTI). Returns
        True if a trap was taken, False if none is due.
        """
        mstatus = self.read(0x300)
        mie = self.read(0x304)
        mip = self.read(0x344)

        if not ((mstatus >> 3) & 1):  # MIE disabled -> no interrupts
            return False

        pending = mip & mie           # both enabled and pending
        if not pending:
            return False

        for bit in INTERRUPT_PRIORITY:
            if (pending >> bit) & 1:
                cause = (1 << 31) | bit  # interrupt bit -> mcause high bit set
                if before_exec and pc is not None:
                    mepc = pc
                elif pc is not None and proc.read_pc() == pc:
                    mepc = pc + inst_size
                else:
                    mepc = proc.read_pc()
                self.trap_enter(proc, mcause=cause, mtval=0, mepc=mepc)
                return True
        return False

    def description(self) -> str:
        lines = ["=== CSR Registers ==="]
        names = {v: k for k, v in CSR_ADDR.items()}
        for addr, val in sorted(self._csr.items()):
            name = names.get(addr, f"0x{addr:03x}")
            lines.append(f"  {name:<12} (0x{addr:03x}) = 0x{val:08x}")
        return "\n".join(lines)

    def trap_log_text(self) -> str:
        if not self.trap_log:
            return "(no traps)"
        lines = []
        for e in self.trap_log:
            halt = " -> HALT" if e["halted"] else ""
            pri = f"  priority={e['priority']+1}" if e["kind"] == "INT" and e["priority"] >= 0 else ""
            lines.append(
                f"[{e['kind']}] cycle {e['cycle']:>4}: "
                f"{e['cause_name']:<22} "
                f"mepc=0x{e['mepc']:08x}  mtvec=0x{e['mtvec']:08x}{pri}{halt}"
            )
        return "\n".join(lines)
