__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x10, 0x80000000\n" // Base addr (Set 0, Way 0)
        "li x11, 0x12345678\n" // Data to write
        "li x12, 0x2000\n"     // Offset to keep the same index but change tag

        // 1st write -> Set 0, Way 0
        "sw x11, 0(x10)\n"

        // 2nd write -> Set 0, Way 1
        "add x10, x10, x12\n"
        "sw x11, 0(x10)\n"

        // 3rd write -> Set 0, Way 2
        "add x10, x10, x12\n"  
        "sw x11, 0(x10)\n"

        // 4th write -> Set 0, Way 3
        "add x10, x10, x12\n"  
        "sw x11, 0(x10)\n"

        // 5th write -> Cache is full, so it overwrites Set 0, Way 0 (Round-Robin)
        "add x10, x10, x12\n"
        "sw x11, 0(x10)\n"

        "li x1, 0\n"
        "ebreak\n"
    );
}