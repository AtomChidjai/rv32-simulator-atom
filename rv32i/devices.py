"""Memory-mapped timer, console, and interrupt devices."""

from .constants import MMIO_CONSOLE_OUT, MMIO_CONSOLE_IN

class Timer:
    """RISC-V machine timer (mtime + mtimecmp) memory-mapped at 0x10000010.

    Drives the MTI interrupt: when ``mtime >= mtimecmp`` it sets ``mip.MTIP``
    (bit 7), else clears it. ``time_increment()`` is called once per simulator
    clock by ``Simulator.step`` / ``step_clk``.
    """

    MMIO_MTIME_LO       = 0x10000010
    MMIO_MTIME_HI       = 0x10000014
    MMIO_MTIMECMP_LO    = 0x10000018
    MMIO_MTIMECMP_HI    = 0x1000001C

    def __init__(self, csr):
        self._csr = csr
        self.reset()

    def reset(self) -> None:
        self.mtime = 0
        self.mtimecmp = 0x000000000000FFFF

    def time_increment(self) -> None:
        self.mtime += 1
        if self.mtime >= self.mtimecmp:  # raise mip.MTIP
            self._csr.set_interrupt_pending(7, True)
        else:
            self._csr.set_interrupt_pending(7, False)

    def on_read(self, addr: int, width: int) -> int:
        if addr == self.MMIO_MTIME_LO:
            return self.mtime & 0xFFFFFFFF
        if addr == self.MMIO_MTIME_HI:
            return (self.mtime >> 32) & 0xFFFFFFFF
        if addr == self.MMIO_MTIMECMP_LO:
            return self.mtimecmp & 0xFFFFFFFF
        if addr == self.MMIO_MTIMECMP_HI:
            return (self.mtimecmp >> 32) & 0xFFFFFFFF
        return 0

    def on_write(self, addr: int, val: int, width: int) -> int:
        if addr == self.MMIO_MTIMECMP_LO:
            self.mtimecmp = (self.mtimecmp & 0xFFFFFFFF00000000) | (val & 0xFFFFFFFF)
        elif addr == self.MMIO_MTIMECMP_HI:
            self.mtimecmp = (self.mtimecmp & 0xFFFFFFFF) | ((val & 0xFFFFFFFF) << 32)

        if self.mtime < self.mtimecmp:
            self._csr.set_interrupt_pending(7, False)

# External (machine) interrupt — toggled by the UI button. Acknowledged by a
# write to MMIO_EXT_IRQ_ACK (0x10000020), which clears mip.MEIP.

MMIO_EXT_IRQ_ACK = 0x10000020

def raise_external_irq(csr) -> None:
    csr.set_interrupt_pending(11, True)

def clear_external_irq(csr) -> None:
    csr.set_interrupt_pending(11, False)

def ext_irq_ack_on_read(addr: int, width: int) -> int:
    return 0

# Software interrupt — raised/cleared via a write to MMIO_MSIP (0x10000024):
# bit 0 of the written value sets mip.MSIP.

MMIO_MSIP = 0x10000024

def raise_software_irq(csr) -> None:
    csr.set_interrupt_pending(3, True)

def clear_software_irq(csr) -> None:
    csr.set_interrupt_pending(3, False)

# Console output device: write-only (reads return 0).
def console_out_on_read(addr: int, width: int) -> int:
    return 0

# Console input device: read-only (writes are ignored).
def console_in_on_write(addr: int, val: int, width: int) -> None:
    pass

def register_default_devices(mem, csr, on_console_write=None, on_console_read=None):
    """Wire the standard MMIO device set onto ``mem`` and return the ``Timer``.

    Registers: mtime lo/hi, mtimecmp lo/hi, console_out, console_in,
    ext_irq_ack, msip. ``on_console_write`` is called per char written to the
    console-out device; ``on_console_read`` returns one character or an empty
    string to pause execution until input is available.
    """
    mem.resume_input()
    timer = Timer(csr)
    mem.register_device("mtime_lo", timer.MMIO_MTIME_LO, 4, timer.on_read, timer.on_write)
    mem.register_device("mtime_hi", timer.MMIO_MTIME_HI, 4, timer.on_read, timer.on_write)
    mem.register_device("mtimecmp_lo", timer.MMIO_MTIMECMP_LO, 4, timer.on_read, timer.on_write)
    mem.register_device("mtimecmp_hi", timer.MMIO_MTIMECMP_HI, 4, timer.on_read, timer.on_write)

    def console_out_write(addr: int, val: int, width: int) -> None:
        for i in range(width):
            ch = (val >> (i * 8)) & 0xFF
            if ch != 0 and on_console_write:
                on_console_write(chr(ch))

    def ext_irq_ack_write(addr: int, val: int, width: int) -> None:
        if val != 0:
            clear_external_irq(csr)

    def msip_write(addr: int, val: int, width: int) -> None:
        if val & 1:
            raise_software_irq(csr)
        else:
            clear_software_irq(csr)

    def msip_read(addr: int, width: int) -> int:
        return (csr.read(0x344) >> 3) & 1

    def console_in_read(addr: int, width: int) -> int:
        if on_console_read:
            ch = on_console_read()
            if ch:
                return ord(ch)
            mem.wait_for_input()
            return 0
        return 0

    mem.register_device("console_out", MMIO_CONSOLE_OUT, 4, console_out_on_read, console_out_write)
    mem.register_device("console_in", MMIO_CONSOLE_IN, 4, console_in_read, console_in_on_write)
    mem.register_device("ext_irq_ack", MMIO_EXT_IRQ_ACK, 4, ext_irq_ack_on_read, ext_irq_ack_write)
    mem.register_device("msip", MMIO_MSIP, 4, msip_read, msip_write)

    return timer
