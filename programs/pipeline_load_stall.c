__attribute__((naked)) void _start(void) {
    asm volatile(
        "addi x5, x0, 21\n"
        "addi x6, x2, -16\n"
        "nop\n"
        "nop\n"
        "sw x5, 0(x6)\n"
        "lw x7, 0(x6)\n"
        "add x8, x7, x7\n"
        "ebreak\n"
    );
}
