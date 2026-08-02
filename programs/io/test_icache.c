
__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        "c.li   a0, 1\n"        // 16-bit: cold fetch (miss)
        "c.li   a1, 2\n"        // 16-bit: hit (same block)

        "addi   a0, a0, 10\n"   // 32-bit: hit (same block)
        "addi   a0, a0, 100\n"  // 32-bit: hit (straddles word boundary,
                                 //          but 1 access — line resident)

        "c.ebreak\n"            // 16-bit: hit (same block)
    );
}
