__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        "c.li   a0, 10\n"       // a0 = 10
        "c.li   a1, 5\n"        // a1 = 5

        "c.addi a0, 2\n"        // a0 += 2   (a0 = 12)
        "c.add  a0, a1\n"       // a0 += a1  (a0 = 17)
        "c.sub  a0, a1\n"       // a0 -= a1  (a0 = 12)
        "c.slli a0, 1\n"        // a0 <<= 1  (a0 = 24)

        "addi a0, a0, 1\n"        // a0 += 1   (a0 = 25)

        "c.ebreak\n"            // 16-bit breakpoint
    );
}