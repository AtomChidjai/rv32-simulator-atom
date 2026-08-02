__attribute__((naked)) void _start(void) {
    asm volatile(
        "addi x1, x0, 5\n"
        "add x2, x1, x1\n"
        "add x3, x2, x1\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "ebreak\n"
    );
}
