#define ADDR_A      0x00001000   // Index 0x40, Tag 0
#define ADDR_B      0x00002000   // Index 0x80, Tag 0
#define CONFLICT_A  0x00021000   // Index 0x40, Tag 1 (ADDR_A)

__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        "li   t1, 0xFF\n"        // Dummy data

        // 1. Cold Misses
        "li   t0, %[addr_a]\n"
        "sw   t1, 0(t0)\n"       // MISS

        "li   t0, %[addr_b]\n"
        "sw   t1, 0(t0)\n"       // MISS

        // 2. Hits
        "li   t0, %[addr_a]\n"
        "lw   t2, 0(t0)\n"       // HIT

        // 3. Conflict Miss (Eviction)
        "li   t0, %[conflict_a]\n"
        "sw   t1, 0(t0)\n"       // MISS

        // 4. Verify Eviction
        "li   t0, %[addr_a]\n"
        "lw   t2, 0(t0)\n"       // MISS

        // 5. Word Offset
        "li   t0, %[addr_b]\n"
        "lw   t2, 0(t0)\n"       // HIT: Word 0
        "lw   t2, 4(t0)\n"       // HIT: Word 1

        "ebreak\n"
        :
        : [addr_a]     "i"(ADDR_A),
          [addr_b]     "i"(ADDR_B),
          [conflict_a] "i"(CONFLICT_A)
    );
}