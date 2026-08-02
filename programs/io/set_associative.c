// Two-way conflict-absorption demo.

__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x10, 0x80000000\n" // Address A (Set 0, Way 0)
        "li x12, 0x4000\n"     // Stride: same set, different tag
        "add x11, x10, x12\n"  // Address B (Set 0, Way 1) — same set, own way
        "li x9,  0xAA\n"       // Dummy data

        "sw x9, 0(x10)\n"      // A -> MISS (Way 0)
        "sw x9, 0(x11)\n"      // B -> MISS (Way 1) — set has a free way, no eviction

        "lw x1, 0(x10)\n"      // A -> HIT
        "lw x2, 0(x11)\n"      // B -> HIT
        "lw x3, 0(x10)\n"      // A -> HIT
        "lw x4, 0(x11)\n"      // B -> HIT

        "li x1, 0\n"
        "ebreak\n"
    );
}
