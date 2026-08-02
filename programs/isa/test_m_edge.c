__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x1, 0\n li x2, 0\n li x3, 0\n li x4, 0\n li x5, 0\n li x6, 0\n"
        "li x7, 0\n li x8, 0\n li x9, 0\n li x10, 0\n li x11, 0\n li x12, 0\n"
        "li x13, 0\n li x14, 0\n li x15, 0\n li x16, 0\n li x17, 0\n li x18, 0\n"
        "li x19, 0\n li x20, 0\n li x21, 0\n li x22, 0\n li x23, 0\n li x24, 0\n"
        "li x25, 0\n li x26, 0\n li x27, 0\n li x28, 0\n li x29, 0\n li x30, 0\n"
        "li x31, 0\n"
        /* 32-bit overflow: 0x10000 * 0x10000 = 0x1_0000_0000 → low=0, high=1. */
        "li x1, 0x10000\n"
        "li x2, 0x10000\n"
        "mul x3, x1, x2\n"
        "mulh x4, x1, x2\n"
        /* INT_MIN * -1: the classic signed overflow boundary. */
        "li x5, 0x80000000\n"
        "li x6, -1\n"
        "mulh x7, x5, x6\n"
        "mulhsu x8, x5, x6\n"
        /* Division edge cases: x/0 and INT_MIN/-1 (architecturally defined). */
        "li x9, 100\n"
        "li x10, 0\n"
        "div x11, x9, x10\n"     /* signed div-by-zero → -1 */
        "divu x12, x9, x10\n"    /* unsigned div-by-zero → 2^32-1 */
        "rem x13, x9, x10\n"     /* signed rem-by-zero → dividend */
        "remu x14, x9, x10\n"    /* unsigned rem-by-zero → dividend */
        "li x15, 0x80000000\n"
        "li x16, -1\n"
        "div x17, x15, x16\n"    /* INT_MIN / -1 → INT_MIN (overflow) */
        "rem x18, x15, x16\n"    /* INT_MIN % -1 → 0 (overflow) */
        "ebreak\n"
    );
}
