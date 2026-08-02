// Direct-mapped conflict demo.

__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x10, 0x80000000\n" // Address A (Set 0, Tag T)
        "li x12, 0x8000\n"     // Stride = num_sets × block_size (one set-index repeat)
        "add x11, x10, x12\n"  // Address B (Set 0, Tag T+1) — aliases A
        "li x9,  0xAA\n"       // Dummy data to store

        "sw x9, 0(x10)\n"      // A -> MISS (fill)
        "sw x9, 0(x11)\n"      // B -> MISS (evicts A)
        "lw x1, 0(x10)\n"      // A -> MISS (evicts B)
        "lw x2, 0(x11)\n"      // B -> MISS (evicts A)
        "lw x3, 0(x10)\n"      // A -> MISS (evicts B)

        "li x1, 0\n"
        "ebreak\n"
    );
}
