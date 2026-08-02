volatile int handler_order[8] = {0};
volatile int handler_idx = 0;

__attribute__((naked))
void trap_handler(void) {
    __asm__ volatile (
        "csrw mscratch, t0\n"
        "csrw 0x34A, t1\n"

        // save mcause to scratch CSR
        "csrr t1, mcause\n"
        "csrw 0x34B, t1\n"

        // compute &handler_order[handler_idx]
        "la   t0, handler_idx\n"
        "lw   t0, 0(t0)\n"
        "slli t0, t0, 2\n"
        "la   t1, handler_order\n"
        "add  t0, t0, t1\n"

        // store mcause at handler_order[handler_idx]
        "csrr t1, 0x34B\n"
        "sw   t1, 0(t0)\n"

        // handler_idx++
        "la   t0, handler_idx\n"
        "lw   t1, 0(t0)\n"
        "addi t1, t1, 1\n"
        "sw   t1, 0(t0)\n"

        // if mcause == 0x8000000B -> ack external
        "csrr t1, 0x34B\n"
        "li   t0, 0x8000000B\n"
        "bne  t1, t0, 1f\n"
        "li   t0, 0x10000020\n"
        "li   t1, 1\n"
        "sw   t1, 0(t0)\n"
        "j    2f\n"

        // if mcause == 0x80000007 -> reschedule timer
    "1:\n"
        "csrr t1, 0x34B\n"
        "li   t0, 0x80000007\n"
        "bne  t1, t0, 2f\n"
        "li   t0, 0x10000010\n"
        "lw   t1, 0(t0)\n"
        "addi t1, t1, 500\n"
        "li   t0, 0x10000018\n"
        "sw   t1, 0(t0)\n"
        "li   t0, 0x1000001C\n"
        "sw   zero, 0(t0)\n"

    "2:\n"
        "csrr t1, 0x34A\n"
        "csrr t0, mscratch\n"
        "mret\n"
    );
}

__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        // mtvec = trap_handler
        "la   t0, trap_handler\n"
        "csrw mtvec, t0\n"

        // enable MEIE (bit 11) + MTIE (bit 7)
        "li   t0, 0x880\n"
        "csrs mie, t0\n"

        // enable MIE (mstatus bit 3)
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

        // print "PRIO\n"
        "li   t0, 0x10000000\n"
        "li   t1, 80\n"
        "sb   t1, 0(t0)\n"
        "li   t1, 82\n"
        "sb   t1, 0(t0)\n"
        "li   t1, 73\n"
        "sb   t1, 0(t0)\n"
        "li   t1, 79\n"
        "sb   t1, 0(t0)\n"
        "li   t1, 10\n"
        "sb   t1, 0(t0)\n"

        "ebreak\n"
    );
}
