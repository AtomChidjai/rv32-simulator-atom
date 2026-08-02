// Machine software-interrupt demo.

int trap_count = 0;   // increments each time the handler fires

void trap_handler(void) __attribute__((interrupt("machine")));
void trap_handler(void) {
    trap_count++;

    __asm__ volatile ("csrrc zero, mip, %0" :: "r"(1 << 3));
}

void _start() {
    __asm__ volatile ("csrrw zero, mtvec, %0" :: "r"((int)trap_handler));

    __asm__ volatile ("csrrs zero, mie, %0" :: "r"(1 << 3));

    __asm__ volatile ("csrrs zero, mstatus, %0" :: "r"(1 << 3));

    __asm__ volatile ("csrrs zero, mip, %0" :: "r"(1 << 3));

    __asm__ volatile ("ebreak");
}
