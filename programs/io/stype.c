void _start() {
    register int data asm("a3") = 0x85F01234;
    int *base_addr = (int *)100;
    __asm__ volatile ("la    gp, __global_pointer$");
    // 1. SB (Store Byte): address 0x00 = 0x85 (data & 0xFF)
    __asm__ volatile ("sb    %0, 0(%1)" : : "r"(data), "r"(base_addr) : "memory");
    // 2. SH (Store Halfword): address 0x00 = 0x1234 (data & 0xFFFF)
    __asm__ volatile ("sh    %0, 4(%1)" : : "r"(data), "r"(base_addr) : "memory");
    // 3. SW (Store Word): address 0x00 = 0x85F01234 (data & 0xFFFFFFFF)
    __asm__ volatile ("sw    %0, 8(%1)" : : "r"(data), "r"(base_addr) : "memory");
    __asm__ volatile ("ebreak");
}
