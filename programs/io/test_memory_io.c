__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        // ===== Memory byte store/load =====
        "li   t0, 0x00002000\n"      // base address for memory tests
        "li   t1, 0xAB\n"
        "sb   t1, 0(t0)\n"           // store byte 0xAB at 0x2000
        "lb   t2, 0(t0)\n"           // load signed byte -> t2 = 0xFFFFFFAB
        "lbu  t3, 0(t0)\n"           // load unsigned byte -> t3 = 0x000000AB

        "li   t1, 0x7F\n"
        "sb   t1, 1(t0)\n"           // store byte 0x7F at 0x2001
        "lb   t4, 1(t0)\n"           // load signed byte -> t4 = 0x0000007F (positive)
        "lbu  t5, 1(t0)\n"           // load unsigned byte -> t5 = 0x0000007F

        // ===== Memory halfword store/load =====
        "li   t1, 0x1234\n"
        "sh   t1, 4(t0)\n"           // store halfword 0x1234 at 0x2004
        "lh   a0, 4(t0)\n"           // load signed halfword -> a0 = 0x00001234
        "lhu  a1, 4(t0)\n"           // load unsigned halfword -> a1 = 0x00001234

        "li   t1, 0x8001\n"
        "sh   t1, 6(t0)\n"           // store halfword 0x8001 at 0x2006
        "lh   a2, 6(t0)\n"           // load signed halfword -> a2 = 0xFFFF8001
        "lhu  a3, 6(t0)\n"           // load unsigned halfword -> a3 = 0x00008001

        // ===== Memory word store/load =====
        "li   t1, 0xDEADBEEF\n"
        "sw   t1, 8(t0)\n"           // store word at 0x2008
        "lw   a4, 8(t0)\n"           // load word -> a4 = 0xDEADBEEF

        "li   t1, 0x00000000\n"
        "sw   t1, 12(t0)\n"          // store zero at 0x200C
        "lw   a5, 12(t0)\n"          // load word -> a5 = 0x00000000

        // ===== Console output (write characters) =====
        "li   s0, 0x10000000\n"      // console_out MMIO address

        "li   s1, 72\n"              // 'H'
        "sb   s1, 0(s0)\n"
        "li   s1, 105\n"             // 'i'
        "sb   s1, 0(s0)\n"
        "li   s1, 33\n"              // '!'
        "sb   s1, 0(s0)\n"
        "li   s1, 10\n"              // '\n'
        "sb   s1, 0(s0)\n"

        // ===== Console output via word store =====
        // Store "OK\n\0" as little-endian word: 0x000A4B4F
        "li   s1, 0x000A4B4F\n"
        "sw   s1, 0(s0)\n"

        // ===== Console input (read one character) =====
        "li   s2, 0x10000004\n"      // console_in MMIO address
        "lb   s3, 0(s2)\n"           // read byte from console_in

        // ===== Echo back the read character =====
        "sb   s3, 0(s0)\n"           // write it to console_out
        "li   s1, 10\n"              // '\n'
        "sb   s1, 0(s0)\n"

        // ===== Verify memory contents after I/O =====
        "lw   s4, 8(t0)\n"           // reload 0xDEADBEEF -> s4
        "lb   s5, 0(t0)\n"           // reload 0xAB signed -> s5 = 0xFFFFFFAB

        "ebreak\n"
    );
}
