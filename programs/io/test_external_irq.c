volatile int irq_count = 0;

__attribute__((naked))
void trap_handler(void) {
    __asm__ volatile (
        "csrw mscratch, t0\n"
        "csrw 0x34A, t1\n"

        "csrr t1, mcause\n"

        // increment irq_count
        "la   t0, irq_count\n"
        "lw   t0, 0(t0)\n"
        "addi t0, t0, 1\n"
        "la   t2, irq_count\n"
        "sw   t0, 0(t2)\n"

        // ack based on mcause
        // MEI (0x8000000B) -> clear via MMIO ack register
        "li   t0, 0x8000000B\n"
        "bne  t1, t0, 1f\n"
        "li   t0, 0x10000020\n"
        "li   t1, 1\n"
        "sw   t1, 0(t0)\n"
        "j    3f\n"

        // MSI (0x80000003) -> clear msip register
    "1:\n"
        "li   t0, 0x80000003\n"
        "bne  t1, t0, 2f\n"
        "li   t0, 0x10000024\n"
        "sw   zero, 0(t0)\n"
        "j    3f\n"

        // MTI (0x80000007) -> reschedule timer
    "2:\n"
        "li   t0, 0x80000007\n"
        "bne  t1, t0, 3f\n"
        "li   t0, 0x10000010\n"
        "lw   t1, 0(t0)\n"
        "addi t1, t1, 500\n"
        "li   t0, 0x10000018\n"
        "sw   t1, 0(t0)\n"
        "li   t0, 0x1000001C\n"
        "sw   zero, 0(t0)\n"

    "3:\n"
        "csrr t1, 0x34A\n"
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

        // enable MEIE (mie bit 11) + MSIE (bit 3)
        "li   t0, 0x808\n"
        "csrs mie, t0\n"

        // enable MIE (mstatus bit 3)
        "li   t0, 0x08\n"
        "csrs mstatus, t0\n"

        // write 'W' to console = waiting for IRQ button
        "li   t0, 0x10000000\n"
        "li   t1, 87\n"          // 'W'
        "sb   t1, 0(t0)\n"
        "li   t1, 65\n"          // 'A'
        "sb   t1, 0(t0)\n"
        "li   t1, 73\n"          // 'I'
        "sb   t1, 0(t0)\n"
        "li   t1, 84\n"          // 'T'
        "sb   t1, 0(t0)\n"
        "li   t1, 10\n"          // '\n'
        "sb   t1, 0(t0)\n"

        // spin until irq_count >= 3
    "1:\n"
        "la   t0, irq_count\n"
        "lw   t1, 0(t0)\n"
        "li   t0, 3\n"
        "blt  t1, t0, 1b\n"

        // done
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
