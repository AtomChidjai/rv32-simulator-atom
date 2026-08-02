__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x1, 0\n li x2, 0\n li x3, 0\n li x4, 0\n li x5, 0\n li x6, 0\n"
        "li x7, 0\n li x8, 0\n li x9, 0\n li x10, 0\n li x11, 0\n li x12, 0\n"
        "li x13, 0\n li x14, 0\n li x15, 0\n li x16, 0\n li x17, 0\n li x18, 0\n"
        "li x19, 0\n li x20, 0\n li x21, 0\n li x22, 0\n li x23, 0\n li x24, 0\n"
        "li x25, 0\n li x26, 0\n li x27, 0\n li x28, 0\n li x29, 0\n li x30, 0\n"
        "li x31, 0\n"
        "li x1, 0x80010000\n"
        /* Store a word with high bits set in each byte, then read it back at
         * every width and offset to exercise sign vs. zero extension. */
        "li x2, 0x80FF7F01\n"
        "sw x2, 0(x1)\n"
        "lb x3, 0(x1)\n"    /* byte 0 = 0x01 → 0x00000001 */
        "lb x4, 1(x1)\n"    /* byte 1 = 0x7F → 0x0000007F */
        "lb x5, 2(x1)\n"    /* byte 2 = 0xFF → 0xFFFFFFFF (sign-extended) */
        "lb x6, 3(x1)\n"    /* byte 3 = 0x80 → 0xFFFFFF80 (sign-extended) */
        "lbu x7, 2(x1)\n"   /* unsigned byte 2 → 0x000000FF */
        "lh x8, 0(x1)\n"    /* halfword 0 = 0x7F01 → 0x00007F01 */
        "lh x9, 2(x1)\n"    /* halfword 1 = 0x80FF → 0xFFFF80FF (sign-extended) */
        "lhu x10, 2(x1)\n"  /* unsigned halfword 1 → 0x000080FF */
        /* Sub-word store then re-read the full word: proves sb only touches
         * its target byte and leaves the rest intact. */
        "li x11, 0xAB\n"
        "sb x11, 1(x1)\n"
        "lw x12, 0(x1)\n"   /* 0x80FFAB01 */
        /* Halfword store overwrites bytes 2-3 only. */
        "li x13, 0x1234\n"
        "sh x13, 2(x1)\n"
        "lw x14, 0(x1)\n"   /* 0x1234AB01 */
        "ebreak\n"
    );
}
