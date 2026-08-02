volatile char test_byte __attribute__((aligned(4))) = 0x85;
volatile short test_half __attribute__((aligned(4))) = (short)0x85F0;
volatile int test_word __attribute__((aligned(4))) = 0x85F01234;

void _start() {
    register int result asm("a3") = 0;
    __asm__ volatile ("la    gp, __global_pointer$");
    // 1. LB  (Load Byte Signed):       0x85 -> sign-extend  -> -123 (0xFFFFFF85)
    __asm__ volatile ("lb    %0, 0(%1)" : "=r"(result) : "r"(&test_byte));
    // 2. LBU (Load Byte Unsigned):     0x85 -> zero-extend  ->  133 (0x00000085)
    __asm__ volatile ("lbu   %0, 0(%1)" : "=r"(result) : "r"(&test_byte));
    // 3. LH  (Load Halfword Signed):   0x85F0 -> sign-extend -> -31248 (0xFFFF85F0)
    __asm__ volatile ("lh    %0, 0(%1)" : "=r"(result) : "r"(&test_half));
    // 4. LHU (Load Halfword Unsigned): 0x85F0 -> zero-extend ->  34288 (0x000085F0)
    __asm__ volatile ("lhu   %0, 0(%1)" : "=r"(result) : "r"(&test_half));
    // 5. LW  (Load Word):              0x85F01234
    __asm__ volatile ("lw    %0, 0(%1)" : "=r"(result) : "r"(&test_word));
    __asm__ volatile ("ebreak");
}
