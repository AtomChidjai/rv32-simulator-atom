void _start() {
    register int val_10     asm("a1") = 10;
    register int val_minus5 asm("a2") = -5;
    register int val_10_2   asm("a3") = 10;

    // 1. BEQ (Branch ==) : branch if a1 == a3
    __asm__ volatile (
        "beq %0, %1, 1f \n\t"
        "nop \n\t"
        "1:\n\t"
        "nop"
        : : "r"(val_10), "r"(val_10_2)
    );

    // 2. BNE (Branch !=) : branch if a1 != a2
    __asm__ volatile (
        "bne %0, %1, 2f \n\t"
        "nop \n\t"
        "2:\n\t"
        "nop"
        : : "r"(val_10), "r"(val_minus5)
    );

    // 3. BLT (Branch < Signed) : branch if a2 < a1
    __asm__ volatile (
        "blt %0, %1, 3f \n\t"
        "nop \n\t"
        "3:\n\t"
        "nop"
        : : "r"(val_minus5), "r"(val_10)
    );

    // 4. BGE (Branch >= Signed) : branch if a1 >= a2
    __asm__ volatile (
        "bge %0, %1, 4f \n\t"
        "nop \n\t"
        "4:\n\t"
        "nop"
        : : "r"(val_10), "r"(val_minus5)
    );

    // 5. BLTU (Branch < Unsigned) : branch if a1 < a2 (unsigned)
    __asm__ volatile (
        "bltu %0, %1, 5f \n\t"
        "nop \n\t"
        "5:\n\t"
        "nop"
        : : "r"(val_10), "r"(val_minus5)
    );

    // 6. BGEU (Branch >= Unsigned) : branch if a2 >= a1 (unsigned)
    __asm__ volatile (
        "bgeu %0, %1, 6f \n\t"
        "nop \n\t"
        "6:\n\t"
        "nop"
        : : "r"(val_minus5), "r"(val_10)
    );

    __asm__ volatile ("ebreak");
}
