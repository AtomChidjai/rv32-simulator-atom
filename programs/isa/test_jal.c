__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x1, 0\n li x2, 0\n li x3, 0\n li x4, 0\n li x5, 0\n li x6, 0\n"
        "li x7, 0\n li x8, 0\n li x9, 0\n li x10, 0\n li x11, 0\n li x12, 0\n"
        "li x13, 0\n li x14, 0\n li x15, 0\n li x16, 0\n li x17, 0\n li x18, 0\n"
        "li x19, 0\n li x20, 0\n li x21, 0\n li x22, 0\n li x23, 0\n li x24, 0\n"
        "li x25, 0\n li x26, 0\n li x27, 0\n li x28, 0\n li x29, 0\n li x30, 0\n"
        "li x31, 0\n"
        /* JAL forward jump: must skip the "bad" sentinel instruction. */
        "jal x1, L1\n"
        "li x2, 0xBAD\n"
        "L1:\n"
        "li x2, 1\n"
        /* Call/return: jal into func; func returns via jalr (ret) to the
         * instruction after the jal (the unconditional j). The fall-through
         * sentinel must be skipped by the return. */
        "jal x1, func\n"
        "j after\n"
        "func:\n"
        "li x3, 7\n"
        "jalr x0, x1, 0\n"
        "li x3, 0xBAD\n"
        "after:\n"
        "li x4, 1\n"
        /* Normalize the address-dependent link register so the Spike-vs-sim
         * comparison (which run at different load addresses) is on equal
         * footing — control flow is what's under test, not PC arithmetic. */
        "li x1, 0xAA\n"
        "ebreak\n"
    );
}
