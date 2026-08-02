__attribute__((naked)) void _start(void) {
    asm volatile(
        "lui   x5,  0x1\n"
        "sw    x9,  0(x5)\n"  
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "nop\n"
        "ebreak\n"
    );
}
