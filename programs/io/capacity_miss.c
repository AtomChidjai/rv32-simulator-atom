// One-KiB direct-mapped capacity-miss demo.

__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x10, 0x80000000\n" // Base address
        "li x12, 64\n"         // Stride = one block (64 B) — each step is a new block, new set
        "li x13, 17\n"         // Number of blocks to touch (num_lines + 1 for a 1 KB cache)
        "li x14, 0\n"          // Loop counter

        "1:\n"
        "add x15, x10, x14\n"  // address = base + counter (counter is the block index)
        "mul x15, x15, x12\n"  //   × 64 -> each block 64 B apart
        "lw x1, 0(x15)\n"      // MISS (cold)
        "addi x14, x14, 1\n"   // counter++
        "blt x14, x13, 1b\n"   // loop while counter < 17

        "lw x2, 0(x10)\n"      // MISS (capacity)

        "li x1, 0\n"
        "ebreak\n"
    );
}
