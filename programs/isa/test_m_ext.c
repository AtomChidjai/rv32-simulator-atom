__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x1, 7\n"
        "li x2, 3\n"
        "mul x3, x1, x2\n"
        "mulh x4, x1, x2\n"
        "li x5, -1\n"
        "mulh x6, x5, x5\n"
        "mulhsu x7, x5, x2\n"
        "mulhu x8, x1, x2\n"
        "div x9, x1, x2\n"
        "divu x10, x1, x2\n"
        "rem x11, x1, x2\n"
        "remu x12, x1, x2\n"
        "li x13, 0\n"
        "div x14, x1, x13\n"
        "rem x15, x1, x13\n"
        "ebreak\n"
    );
}
