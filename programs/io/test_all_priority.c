volatile int idx = 0;

__attribute__((naked))
void trap_handler(void) {
    __asm__ volatile (
        "csrw mscratch, t0\n"
        "csrw 0x34A, t1\n"

        "csrr t1, mcause\n"

        // idx++
        "la   t0, idx\n"
        "lw   t2, 0(t0)\n"
        "addi t2, t2, 1\n"
        "sw   t2, 0(t0)\n"

        // print interrupt name
        "li   t0, 0x8000000B\n"
        "bne  t1, t0, 40f\n"
        "li   t0, 0x10000000\n"
        "li   t2, 69\n"   // E
        "sb   t2, 0(t0)\n"
        "li   t2, 88\n"   // X
        "sb   t2, 0(t0)\n"
        "li   t2, 84\n"   // T
        "sb   t2, 0(t0)\n"
        "li   t2, 32\n"   // space
        "sb   t2, 0(t0)\n"
        "j    1f\n"
    "40:\n"
        "li   t0, 0x80000003\n"
        "bne  t1, t0, 41f\n"
        "li   t0, 0x10000000\n"
        "li   t2, 83\n"   // S
        "sb   t2, 0(t0)\n"
        "li   t2, 87\n"   // W
        "sb   t2, 0(t0)\n"
        "li   t2, 73\n"   // I
        "sb   t2, 0(t0)\n"
        "li   t2, 32\n"   // space
        "sb   t2, 0(t0)\n"
        "j    1f\n"
    "41:\n"
        "li   t0, 0x80000007\n"
        "bne  t1, t0, 1f\n"
        "li   t0, 0x10000000\n"
        "li   t2, 84\n"   // T
        "sb   t2, 0(t0)\n"
        "li   t2, 73\n"   // I
        "sb   t2, 0(t0)\n"
        "li   t2, 77\n"   // M
        "sb   t2, 0(t0)\n"
        "li   t2, 32\n"   // space
        "sb   t2, 0(t0)\n"

    "1:\n"
        // ack external
        "li   t0, 0x8000000B\n"
        "bne  t1, t0, 2f\n"
        "li   t0, 0x10000020\n"
        "li   t1, 1\n"
        "sw   t1, 0(t0)\n"
        "j    4f\n"

        // ack software
    "2:\n"
        "li   t0, 0x80000003\n"
        "bne  t1, t0, 3f\n"
        "li   t0, 0x10000024\n"
        "sw   zero, 0(t0)\n"
        "j    4f\n"

        // reschedule timer
    "3:\n"
        "li   t0, 0x80000007\n"
        "bne  t1, t0, 4f\n"
        "li   t0, 0x10000010\n"
        "lw   t1, 0(t0)\n"
        "addi t1, t1, 500\n"
        "li   t0, 0x10000018\n"
        "sw   t1, 0(t0)\n"
        "li   t0, 0x1000001C\n"
        "sw   zero, 0(t0)\n"

    "4:\n"
        "csrr t1, 0x34A\n"
        "csrr t0, mscratch\n"
        "mret\n"
    );
}

__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        "la   t0, trap_handler\n"
        "csrw mtvec, t0\n"

        // enable MEIE (11) + MSIE (3) + MTIE (7)
        "li   t0, 0x888\n"
        "csrs mie, t0\n"

        // enable MIE
        "li   t0, 0x08\n"
        "csrs mstatus, t0\n"

        // mtimecmp = mtime + 5
        "li   t0, 0x10000010\n"
        "lw   t1, 0(t0)\n"
        "addi t1, t1, 5\n"
        "li   t0, 0x10000018\n"
        "sw   t1, 0(t0)\n"
        "li   t0, 0x1000001C\n"
        "sw   zero, 0(t0)\n"

        // spin until idx >= 2 (at least 2 interrupts handled)
    "0:\n"
        "la   t0, idx\n"
        "lw   t1, 0(t0)\n"
        "li   t0, 2\n"
        "blt  t1, t0, 0b\n"

        // newline
        "li   t0, 0x10000000\n"
        "li   t1, 10\n"
        "sb   t1, 0(t0)\n"

        "ebreak\n"
    );
}
