__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x1, 10\n"
        "addi x2, x1, 5\n"
        "xori x3, x1, 0xFF\n"
        "ori  x4, x1, 0xF0\n"
        "andi x5, x1, 0x0F\n"
        "slli x6, x1, 3\n"
        "li x7, 0x80000000\n"
        "srli x8, x7, 4\n"
        "srai x9, x7, 4\n"
        "slti x10, x1, 20\n"
        "slti x11, x1, 5\n"
        "sltiu x12, x1, 20\n"
        "addi x13, x1, -1\n"
        "addi x14, x0, 0\n"
        "ebreak\n"
    );
}
