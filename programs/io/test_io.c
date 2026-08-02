__attribute__((naked))
void _start(void) {
    __asm__ volatile (
        "li   t0, 0x10000000\n"
        
        "li   t1, 72\n"           // 'H'
        "sb   t1, 0(t0)\n"
        "li   t1, 101\n"          // 'e'
        "sb   t1, 0(t0)\n"
        "li   t1, 108\n"          // 'l'
        "sb   t1, 0(t0)\n"
        "li   t1, 108\n"          // 'l'
        "sb   t1, 0(t0)\n"
        "li   t1, 111\n"          // 'o'
        "sb   t1, 0(t0)\n"
        "li   t1, 10\n"           // '\n'
        "sb   t1, 0(t0)\n"

        "ebreak\n"
    );
}
