volatile int first_cause = 0;

__attribute__((naked))
void trap_handler(void) {
    __asm__ volatile (
        "csrw mscratch, t0\n"
        "csrw 0x34A, t1\n"

        "csrr t1, mcause\n"

        // if first_cause == 0, record it
        "la   t0, first_cause\n"
        "lw   t0, 0(t0)\n"
        "bnez t0, 1f\n"
        "la   t0, first_cause\n"
        "sw   t1, 0(t0)\n"

    "1:\n"
        // ack external
        "li   t0, 0x8000000B\n"
        "bne  t1, t0, 2f\n"
        "li   t0, 0x10000020\n"
        "li   t1, 1\n"
        "sw   t1, 0(t0)\n"
        "j    3f\n"

        // reschedule timer
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
        "la   t0, trap_handler\n"
        "csrw mtvec, t0\n"

        // enable MEIE + MTIE
        "li   t0, 0x880\n"
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

        // spin until first_cause != 0
    "0:\n"
        "la   t0, first_cause\n"
        "lw   t1, 0(t0)\n"
        "beqz t1, 0b\n"

        // t1 = first_cause
        // if 0x80000007 (timer) -> print "TIMER FIRST"
        "li   t0, 0x80000007\n"
        "bne  t1, t0, 1f\n"
        "li   t0, 0x10000000\n"
        "li   t1, 84\n"   // T
        "sb   t1, 0(t0)\n"
        "li   t1, 73\n"   // I
        "sb   t1, 0(t0)\n"
        "li   t1, 77\n"   // M
        "sb   t1, 0(t0)\n"
        "li   t1, 69\n"   // E
        "sb   t1, 0(t0)\n"
        "li   t1, 82\n"   // R
        "sb   t1, 0(t0)\n"
        "li   t1, 32\n"   // space
        "sb   t1, 0(t0)\n"
        "li   t1, 70\n"   // F
        "sb   t1, 0(t0)\n"
        "li   t1, 73\n"   // I
        "sb   t1, 0(t0)\n"
        "li   t1, 82\n"   // R
        "sb   t1, 0(t0)\n"
        "li   t1, 83\n"   // S
        "sb   t1, 0(t0)\n"
        "li   t1, 84\n"   // T
        "sb   t1, 0(t0)\n"
        "li   t1, 10\n"   // \n
        "sb   t1, 0(t0)\n"
        "j    2f\n"

        // if 0x8000000B (external) -> print "EXT FIRST"
    "1:\n"
        "li   t0, 0x8000000B\n"
        "bne  t1, t0, 2f\n"
        "li   t0, 0x10000000\n"
        "li   t1, 69\n"   // E
        "sb   t1, 0(t0)\n"
        "li   t1, 88\n"   // X
        "sb   t1, 0(t0)\n"
        "li   t1, 84\n"   // T
        "sb   t1, 0(t0)\n"
        "li   t1, 32\n"   // space
        "sb   t1, 0(t0)\n"
        "li   t1, 70\n"   // F
        "sb   t1, 0(t0)\n"
        "li   t1, 73\n"   // I
        "sb   t1, 0(t0)\n"
        "li   t1, 82\n"   // R
        "sb   t1, 0(t0)\n"
        "li   t1, 83\n"   // S
        "sb   t1, 0(t0)\n"
        "li   t1, 84\n"   // T
        "sb   t1, 0(t0)\n"
        "li   t1, 10\n"   // \n
        "sb   t1, 0(t0)\n"

    "2:\n"
        "ebreak\n"
    );
}
