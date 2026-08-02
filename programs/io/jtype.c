void _start() {
    register int link       asm("ra") = 0;
    register int result     asm("a4") = 0;
    register int dummy      asm("a5") = 0;

    // 1. JAL: jump to 1:
    __asm__ volatile (
        "jal   %0, 1f      \n\t"
        "addi  %1, x0, 0   \n\t"  // skipped
        "1:                \n\t"
        "addi  %1, x0, 1"          // ra = pc + 4
        : "=r"(link), "=r"(result)
    );

    // 2. JAL: skipped ebreak
    __asm__ volatile (
        "addi  %1, x0, 0   \n\t"  // reset result
        "jal   %0, 2f      \n\t"
        "ebreak            \n\t"
        "2:                \n\t"
        "addi  %1, x0, 2"
        : "=r"(link), "=r"(result)
        : "0"(link), "1"(result)
    );

    // 3. JAL : jump to 3: then put 3 at ra
    __asm__ volatile (
        "jal   x0, 3f      \n\t"
        "addi  %0, x0, 0   \n\t"  // skipped
        "3:                \n\t"
        "addi  %0, x0, 3"          // ra = 3
        : "=r"(link)
    );

    __asm__ volatile ("ebreak");
}
