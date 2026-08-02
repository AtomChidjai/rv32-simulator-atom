// Minimal machine software-interrupt demo.

volatile int interrupt_seen = 0;

void trap_handler(void) __attribute__((interrupt("machine")));
void trap_handler(void) {
    interrupt_seen = 1;
    __asm__ volatile ("csrc mip, %0" :: "r"(1 << 3));       // clear MSIP
}

void _start(void) {
    __asm__ volatile ("csrw mtvec, %0" :: "r"((int)trap_handler));
    __asm__ volatile ("csrs mie, %0" :: "r"(1 << 3));       // enable MSIE
    __asm__ volatile ("csrs mstatus, %0" :: "r"(1 << 3));   // global MIE
    __asm__ volatile ("csrs mip, %0" :: "r"(1 << 3));       // trigger MSIP

    while (!interrupt_seen) {
    }

    __asm__ volatile ("ebreak");
}
