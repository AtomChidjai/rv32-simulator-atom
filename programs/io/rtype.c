void _start() {
    register int a0 asm("a0") = 15;      
    register int a1 asm("a1") = -10; // 0xFFFFFFF6  
    register int a2 asm("a2") = 2;       
    register int a3 asm("a3") = 0;   

    // 1. ADD: 15 + (-10)a3 = 5
    __asm__ volatile ("add   %0, %1, %2" : "=r"(a3) : "r"(a0), "r"(a1));
    // 2. SUB: 15 - (-10) a3 = 25
    __asm__ volatile ("sub   %0, %1, %2" : "=r"(a3) : "r"(a0), "r"(a1));
    // 3. XOR: 15 ^ 2 (1111 ^ 0010) a3 = 13 (1101)
    __asm__ volatile ("xor   %0, %1, %2" : "=r"(a3) : "r"(a0), "r"(a2));
    // 4. OR: 15 | 2 (1111 | 0010) a3 = 15 (1111)
    __asm__ volatile ("or    %0, %1, %2" : "=r"(a3) : "r"(a0), "r"(a2));
    // 5. AND: 15 & 2 (1111 & 0010) a3 = 2 (0010)
    __asm__ volatile ("and   %0, %1, %2" : "=r"(a3) : "r"(a0), "r"(a2));
    // 6. SLL (Shift Left Logical): 15 << 2 a3 = 60
    __asm__ volatile ("sll   %0, %1, %2" : "=r"(a3) : "r"(a0), "r"(a2));
    // 7. SRL (Shift Right Logical): -10 >> 2 -> unsigned a3 = 1073741821 (0x3FFFFFFD)
    __asm__ volatile ("srl   %0, %1, %2" : "=r"(a3) : "r"(a1), "r"(a2));
    // 8. SRA (Shift Right Arithmetic): -10 >> 2 signed a3 = -3 (0xFFFFFFFD)
    __asm__ volatile ("sra   %0, %1, %2" : "=r"(a3) : "r"(a1), "r"(a2));
    // 9. SLT (Set Less Than - Signed): if -10 < 15 -> a3 = 1
    __asm__ volatile ("slt   %0, %1, %2" : "=r"(a3) : "r"(a1), "r"(a0));
    // 10. SLTU (Set Less Than - Unsigned): if 0xFFFFFFF6 < 15 -> a3 = 0
    __asm__ volatile ("sltu  %0, %1, %2" : "=r"(a3) : "r"(a1), "r"(a0)); 
    __asm__ volatile ("ebreak");
}