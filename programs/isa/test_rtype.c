__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x1, 10\n"
        "li x2, 20\n"
        "add x3, x1, x2\n"
        "sub x4, x2, x1\n"
        "xor x5, x1, x2\n"
        "or  x6, x1, x2\n"
        "and x7, x1, x2\n"
        "li x8, 3\n"
        "sll x9, x1, x8\n"
        "li x10, 0x80000000\n"
        "li x11, 1\n"
        "srl x12, x10, x11\n"
        "sra x13, x10, x11\n"
        "slt x14, x1, x2\n"
        "slt x15, x2, x1\n"
        "sltu x16, x1, x2\n"
        "li x17, -1\n"
        "sltu x18, x1, x17\n"
        "ebreak\n"
    );
}
