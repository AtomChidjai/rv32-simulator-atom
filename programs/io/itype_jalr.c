void _start() {
    register int link    asm("ra") = 0;
    register int result  asm("a4") = 0;
    register int address asm("a5") = 0;

    // 1. JALR: jump to address in register, save return addr in ra
    __asm__ volatile (
        "la    %2, 1f      \n\t"
        "jalr  %0, %2, 0   \n\t"
        "addi  %1, x0, 0   \n\t"
        "1:                \n\t"
        "addi  %1, x0, 1"
        : "=r"(link), "=r"(result), "=r"(address)
    );

    // 2. JALR with immediate offset
    __asm__ volatile (
        "addi  %1, x0, 0   \n\t"
        "la    %2, 2f      \n\t"
        "addi  %2, %2, -4  \n\t"
        "jalr  %0, %2, 4   \n\t"
        "ebreak            \n\t"
        "2:                \n\t"
        "addi  %1, x0, 2"
        : "=r"(link), "=r"(result), "=r"(address)
        : "0"(link), "1"(result), "2"(address)
    );

    // 3. JALR x0: unconditional register jump, no link saved
    __asm__ volatile (
        "la    %1, 3f      \n\t"
        "jalr  x0, %1, 0   \n\t"
        "addi  %0, x0, 0   \n\t"
        "3:                \n\t"
        "addi  %0, x0, 3"
        : "=r"(link), "=r"(result)
        : "0"(link)
    );

    __asm__ volatile ("ebreak");
}
