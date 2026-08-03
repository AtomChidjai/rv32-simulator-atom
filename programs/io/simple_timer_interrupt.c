// The timer fires once, the handler reschedules it, and MRET resumes the loop.

#define MTIME_LO     (*(volatile unsigned int *)0x10000010u)
#define MTIMECMP_LO  (*(volatile unsigned int *)0x10000018u)
#define MTIMECMP_HI  (*(volatile unsigned int *)0x1000001cu)

volatile unsigned int timer_interrupt_seen = 0;

void timer_interrupt_handler(void) __attribute__((interrupt("machine")));
void timer_interrupt_handler(void) {
    unsigned int cause;
    __asm__ volatile ("csrr %0, mcause" : "=r"(cause));

    if (cause == 0x80000007u) {
        MTIMECMP_LO = MTIME_LO + 0x1000u;
        MTIMECMP_HI = 0;
        timer_interrupt_seen = 1;
    }
}

void _start(void) {
    MTIMECMP_LO = MTIME_LO + 200u;
    MTIMECMP_HI = 0;

    __asm__ volatile (
        "csrw mtvec, %0\n"
        "csrs mie, %1\n"
        "csrs mstatus, %2\n"
        :
        : "r"((unsigned int)timer_interrupt_handler),
          "r"(1u << 7),
          "r"(1u << 3)
    );

    while (!timer_interrupt_seen) {
        /* Wait for the machine timer interrupt. */
    }

    __builtin_trap();
}
