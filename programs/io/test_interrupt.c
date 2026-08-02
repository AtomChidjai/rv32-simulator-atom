volatile int irq_count = 0;

__attribute__((naked))
void trap_handler(void) {
    __asm__ volatile (
        "csrw mscratch, t0\n"
        "csrw 0x34A, t1\n"       // save t1 to mtval (unused scratch)

        "la   t0, irq_count\n"
        "lw   t1, 0(t0)\n"
        "addi t1, t1, 1\n"
        "sw   t1, 0(t0)\n"

        // write '!' to console to show interrupt fired
        "li   t0, 0x10000000\n"
        "li   t1, 33\n"          // '!'
        "sb   t1, 0(t0)\n"
        "li   t1, 10\n"          // newline
        "sb   t1, 0(t0)\n"

        // reschedule: mtimecmp = mtime_lo + 20
        "li   t0, 0x10000010\n"  // mtime_lo
        "lw   t1, 0(t0)\n"
        "addi t1, t1, 20\n"
        "li   t0, 0x10000018\n"  // mtimecmp_lo
        "sw   t1, 0(t0)\n"
        "li   t0, 0x1000001C\n"  // mtimecmp_hi = 0
        "sw   zero, 0(t0)\n"

        "csrr t1, 0x34A\n"       // restore t1
        "csrr t0, mscratch\n"
        "mret\n"
    );
}

__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        // set mtvec = trap_handler
        "la   t0, trap_handler\n"
        "csrw mtvec, t0\n"

        // enable MTIE (mie bit 7)
        "li   t0, 0x80\n"
        "csrs mie, t0\n"

        // enable MIE (mstatus bit 3)
        "li   t0, 0x08\n"
        "csrs mstatus, t0\n"

        // set mtimecmp = mtime_lo + 10 (fire after 10 cycles)
        "li   t0, 0x10000010\n"  // mtime_lo
        "lw   t1, 0(t0)\n"
        "addi t1, t1, 10\n"
        "li   t0, 0x10000018\n"  // mtimecmp_lo
        "sw   t1, 0(t0)\n"
        "li   t0, 0x1000001C\n"  // mtimecmp_hi = 0
        "sw   zero, 0(t0)\n"

        // spin until irq_count >= 3
    "1:\n"
        "la   t0, irq_count\n"
        "lw   t1, 0(t0)\n"
        "li   t0, 3\n"
        "blt  t1, t0, 1b\n"

        // done — write 'D','O','N','E','\n' to console
        "li   t0, 0x10000000\n"
        "li   t1, 68\n"          // 'D'
        "sb   t1, 0(t0)\n"
        "li   t1, 79\n"          // 'O'
        "sb   t1, 0(t0)\n"
        "li   t1, 78\n"          // 'N'
        "sb   t1, 0(t0)\n"
        "li   t1, 69\n"          // 'E'
        "sb   t1, 0(t0)\n"
        "li   t1, 10\n"          // '\n'
        "sb   t1, 0(t0)\n"

        "ebreak\n"
    );
}
