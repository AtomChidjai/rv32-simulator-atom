/* Multi-cycle stage-pattern demo. */

__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x10, 5\n"
        "li x11, 7\n"

        "add x12, x10, x11\n"

        "addi x13, x2, -16\n"

        "sw x12, 0(x13)\n"

        "lw x14, 0(x13)\n"

        "beq x10, x10, 1f\n"
        "li x15, 99\n"
        "1:\n"

        "jal x10, 2f\n"
        "li x16, 88\n"
        "2:\n"

        "ebreak\n"
    );
}
