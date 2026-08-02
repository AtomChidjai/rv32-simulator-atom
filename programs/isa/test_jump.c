__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x1, 0\n"
        "jal x2, 1f\n"
        "li x1, 99\n"
        "1:\n"
        "li x3, 0x20000\n"
        "li x4, 0\n"
        "jalr x5, x3, 0\n"
        "li x4, 99\n"
        ".section .text2, \"ax\", @progbits\n"
        ".global target\n"
        "target:\n"
        "li x4, 1\n"
        "ebreak\n"
    );
}
