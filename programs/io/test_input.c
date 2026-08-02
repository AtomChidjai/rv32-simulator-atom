__attribute__((naked))
void _start(void) {
    __asm__ volatile (
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

        // ===== Output the read character =====
        "sb   s3, 0(s0)\n"           // write it to console_out
        "li   s1, 10\n"              // '\n'
        "sb   s1, 0(s0)\n"

        // ===== Verify memory contents after I/O =====
        "lw   s4, 8(t0)\n"           // reload 0xDEADBEEF -> s4
        "lb   s5, 0(t0)\n"           // reload 0xAB signed -> s5 = 0xFFFFFFAB

        "ebreak\n"
    );
}
