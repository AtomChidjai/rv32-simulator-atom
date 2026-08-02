__attribute__((naked)) void _start(void) {
    asm volatile(
        "addi x1, x0, 5\n"
        "addi x2, x0, 10\n"
        "addi x3, x0, 15\n"
        "ebreak\n"
    );
}
