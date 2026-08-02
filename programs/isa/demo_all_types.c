/* Instruction-class demo. */

__attribute__((naked)) void _start(void) {
    asm volatile(
        "lui   x5, 0x1\n"              /* x5 = 0x1000 (data base)        */
        "auipc x6, 0\n"                /* x6 = current PC                */

        "addi  x7, x0, 10\n"           /* x7 = 10                        */
        "addi  x8, x0, 7\n"            /* x8 = 7                         */

        "add   x9,  x7, x8\n"          /* x9  = 17                       */
        "sub   x10, x7, x8\n"          /* x10 = 3                        */

        "mul   x11, x7, x8\n"          /* x11 = 70                       */
        "div   x12, x7, x8\n"          /* x12 = 1 (10/7)                 */

        "sw    x9,  0(x5)\n"           /* mem[0x1000] = 17               */
        "sb    x8,  4(x5)\n"           /* mem[0x1004] low byte = 7       */

        "lw    x12, 0(x5)\n"           /* x12 = 17 (read back)           */
        "lb    x13, 4(x5)\n"           /* x13 = 7  (sign-extended byte)  */

        "beq   x7, x7, 1f\n"           /* always taken                   */
        "addi  x14, x0, 99\n"          /* SKIPPED                        */
        "1:\n"

        "bne   x7, x8, 2f\n"           /* taken (10 != 7)                */
        "addi  x14, x0, 88\n"          /* SKIPPED                        */
        "2:\n"

        "jal   x1, func\n"

        "csrrw x15, mscratch, x7\n"    /* x15 = old mscratch; mscratch=10 */
        "csrrs x16, mscratch, x0\n"    /* x16 = 10 (read mscratch)        */

        "ebreak\n"

        "func:\n"
        "addi  x17, x0, 42\n"          /* x17 = 42                       */
        "jalr  x0, x1, 0\n"            /* return to caller               */
    );
}
