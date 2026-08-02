// Write-allocate/write-through demo.

__attribute__((naked)) void _start(void) {
    asm volatile(
        "li x10, 0x80000000\n" // Cold address (not yet in the cache)
        "li x11, 0xDEADBEEF\n" // Value to store
        "li x12, 0xCAFEBABE\n" // A second value

        "sw x11, 0(x10)\n"     // STORE -> MISS (write-allocate brings block in)

        "lw x1, 0(x10)\n"      // LOAD -> HIT  (x1 == 0xDEADBEEF)

        "sw x12, 4(x10)\n"     // STORE word 1 -> HIT

        "lw x2, 4(x10)\n"      // LOAD -> HIT  (x2 == 0xCAFEBABE)

        "li x1, 0\n"
        "ebreak\n"
    );
}
