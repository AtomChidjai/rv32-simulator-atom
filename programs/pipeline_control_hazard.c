__attribute__((naked)) void _start(void) {
    asm volatile(
        "beq x0, x0, 1f\n"
        "addi x1, x0, 99\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "1:\n"
        "addi x1, x0, 7\n"
        "ebreak\n"
    );
}
