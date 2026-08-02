// Run this program, then click "[!] External" in the GUI trap-log drawer.

#define EXT_IRQ_ACK (*(volatile unsigned int *)0x10000020u)

volatile unsigned int external_interrupt_seen = 0;

void external_interrupt_handler(void) __attribute__((interrupt("machine")));
void external_interrupt_handler(void) {
    unsigned int cause;
    __asm__ volatile ("csrr %0, mcause" : "=r"(cause));

    if (cause == 0x8000000bu) {
        EXT_IRQ_ACK = 1;
        external_interrupt_seen = 1;
    }
}

void _start(void) {
    __asm__ volatile (
        "csrw mtvec, %0\n"
        "csrs mie, %1\n"
        "csrs mstatus, %2\n"
        :
        : "r"((unsigned int)external_interrupt_handler),
          "r"(1u << 11),
          "r"(1u << 3)
    );

    while (!external_interrupt_seen) {
        __asm__ volatile ("nop");
    }

    __asm__ volatile ("ebreak");
}
