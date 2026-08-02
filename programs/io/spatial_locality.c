// Spatial-locality cache demo.

__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x10, 0x80000000\n" // Base of a 4-word run, all in one block

        "lw x1, 0(x10)\n"      // Word 0 -> MISS (cold fill of the block)
        "lw x2, 4(x10)\n"      // Word 1 -> HIT  (same block)
        "lw x3, 8(x10)\n"      // Word 2 -> HIT  (same block)
        "lw x4, 12(x10)\n"     // Word 3 -> HIT  (same block)

        "li x1, 0\n"
        "ebreak\n"
    );
}
