// Four-way FIFO eviction demo.

__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x10, 0x80000000\n" // Address A (Set 0, Way 0)
        "li x11, 0x12345678\n" // Data to write
        "li x12, 0x2000\n"     // Stride: same index, new tag

        "add x13, x10, x12\n"  // Address B
        "add x14, x13, x12\n"  // Address C
        "add x15, x14, x12\n"  // Address D
        "add x16, x15, x12\n"  // Address E (forces eviction)

        "sw x11, 0(x10)\n"     // Write A -> Set 0, Way 0   (FIFO ptr -> 1)
        "sw x11, 0(x13)\n"     // Write B -> Set 0, Way 1   (FIFO ptr -> 2)
        "sw x11, 0(x14)\n"     // Write C -> Set 0, Way 2   (FIFO ptr -> 3)
        "sw x11, 0(x15)\n"     // Write D -> Set 0, Way 3   (FIFO ptr -> 0)

        "sw x11, 0(x16)\n"     // Write E -> Set 0, evicts Way 0 (A).

        "li x1, 0\n"
        "ebreak\n"
    );
}
