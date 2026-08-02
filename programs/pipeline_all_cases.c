__attribute__((naked)) void _start(void) {
    asm volatile(
        // ".option norvc\n"

        /* Independent instructions: normal pipeline flow. */
        "addi x5, x0, 5\n"
        "addi x6, x0, 7\n"

        /* RAW dependency: forwarded when forwarding is on. */
        "add  x7, x5, x6\n"       /* x7 = 12 */

        /* Store can miss in D-cache; load-use inserts one bubble. */
        "addi x8, x2, -16\n"
        "sw   x7, 0(x8)\n"
        "lw   x9, 0(x8)\n"
        "add  x10, x9, x5\n"      /* x10 = 17 */

        /* Taken: predict-not-taken flushes the skipped instruction. */
        "beq  x5, x5, 1f\n"
        "addi x11, x0, 99\n"      /* skipped */
        "1:\n"
        "addi x11, x0, 1\n"

        /* Not taken: predict-taken causes a recovery. */
        "bne  x5, x5, 2f\n"
        "addi x12, x0, 2\n"
        "2:\n"

        "ebreak\n"
    );
}
