__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        // ===== mul =====
        "li   t0, 7\n"
        "li   t1, 3\n"
        "mul  t2, t0, t1\n"      // t2 = 21

        "li   t0, -1\n"
        "li   t1, -1\n"
        "mul  t3, t0, t1\n"      // t3 = 1

        // ===== mulh (signed x signed, upper 32) =====
        "li   t0, 0x7FFFFFFF\n"  // maximum integer
        "li   t1, 2\n"
        "mulh t4, t0, t1\n"      // t4 = 0 (0xFFFFFFFE fits in 32 bits, upper=0)

        "li   t0, 0x80000000\n"  // INT_MIN
        "li   t1, 2\n"
        "mulh a0, t0, t1\n"      // a0 = 0xFFFFFFFF (-0x100000000 >> 32)

        // ===== mulhsu (signed x unsigned, upper 32) =====
        "li   t0, -1\n"
        "li   t1, 1\n"
        "mulhsu a1, t0, t1\n"    // a1 = 0xFFFFFFFF

        // ===== mulhu (unsigned x unsigned, upper 32) =====
        "li   t0, 0xFFFFFFFF\n"
        "li   t1, 0xFFFFFFFF\n"
        "mulhu a2, t0, t1\n"     // a2 = 0xFFFFFFFE

        // ===== div (signed division) =====
        "li   t0, 7\n"
        "li   t1, 3\n"
        "div  a3, t0, t1\n"      // a3 = 2

        "li   t0, -7\n"
        "li   t1, 3\n"
        "div  a4, t0, t1\n"      // a4 = -2 (0xFFFFFFFE)

        "li   t0, 5\n"
        "li   t1, 0\n"
        "div  a5, t0, t1\n"      // a5 = -1 (0xFFFFFFFF, div by zero)

        "li   t0, 0x80000000\n"  // INT_MIN
        "li   t1, -1\n"
        "div  a6, t0, t1\n"      // a6 = 0x80000000 (overflow)

        // ===== divu (unsigned division) =====
        "li   t0, 7\n"
        "li   t1, 3\n"
        "divu a7, t0, t1\n"      // a7 = 2

        "li   t0, 0xFFFFFFFF\n"
        "li   t1, 2\n"
        "divu s2, t0, t1\n"      // s2 = 0x7FFFFFFF

        "li   t0, 5\n"
        "li   t1, 0\n"
        "divu s3, t0, t1\n"      // s3 = 0xFFFFFFFF (div by zero)

        // ===== rem (signed remainder) =====
        "li   t0, 7\n"
        "li   t1, 3\n"
        "rem  s4, t0, t1\n"      // s4 = 1

        "li   t0, -7\n"
        "li   t1, 3\n"
        "rem  s5, t0, t1\n"      // s5 = -1 (0xFFFFFFFF)

        "li   t0, 5\n"
        "li   t1, 0\n"
        "rem  s6, t0, t1\n"      // s6 = 5 (div by zero, returns dividend)

        "li   t0, 0x80000000\n"  // INT_MIN
        "li   t1, -1\n"
        "rem  s7, t0, t1\n"      // s7 = 0 (overflow, returns 0)

        // ===== remu (unsigned remainder) =====
        "li   t0, 7\n"
        "li   t1, 3\n"
        "remu s8, t0, t1\n"      // s8 = 1

        "li   t0, 5\n"
        "li   t1, 0\n"
        "remu s9, t0, t1\n"      // s9 = 5 (div by zero, returns dividend)

        "ebreak\n"
    );
}
