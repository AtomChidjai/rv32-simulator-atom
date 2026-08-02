void _start() {
    register int a0 asm("a0") = 15;      
    register int a1 asm("a1") = -10;     
    register int a3 asm("a3") = 0;       

    // 1. ADDI (Add Immediate): 15 + (-5) = a3 = 10
    __asm__ volatile ("addi  %0, %1, -5" : "=r"(a3) : "r"(a0));
    // 2. XORI (XOR Immediate): 15 ^ 3 (1111 ^ 0011) = a3 = 12 (1100)
    __asm__ volatile ("xori  %0, %1, 3" : "=r"(a3) : "r"(a0));
    // 3. ORI (OR Immediate): 15 | 16 (01111 | 10000) = a3 = 31 (11111)
    __asm__ volatile ("ori   %0, %1, 16" : "=r"(a3) : "r"(a0));
    // 4. ANDI (AND Immediate): 15 & 10 (1111 & 1010) = a3 = 10 (1010)
    __asm__ volatile ("andi  %0, %1, 10" : "=r"(a3) : "r"(a0));
    // 5. SLLI (Shift Left Logical Immediate): 15 << 2 = a3 = 60
    __asm__ volatile ("slli  %0, %1, 2" : "=r"(a3) : "r"(a0));
    // 6. SRLI (Shift Right Logical Immediate): -10 >> 2 = a3 = 1073741821 (0x3FFFFFFD)
    __asm__ volatile ("srli  %0, %1, 2" : "=r"(a3) : "r"(a1));
    // 7. SRAI (Shift Right Arithmetic Immediate): -10 >> 2 = a3 = -3 (0xFFFFFFFD)
    __asm__ volatile ("srai  %0, %1, 2" : "=r"(a3) : "r"(a1));
    // 8. SLTI (Set Less Than Immediate - Signed): if -10 < 15 = a3 = 1
    __asm__ volatile ("slti  %0, %1, 15" : "=r"(a3) : "r"(a1));
    // 9. SLTIU (Set Less Than Immediate - Unsigned): if -10 < 15 (unsigned) = a3 = 0
    __asm__ volatile ("sltiu %0, %1, 15" : "=r"(a3) : "r"(a1));
    // จบการทำงาน
    __asm__ volatile ("ebreak");
}