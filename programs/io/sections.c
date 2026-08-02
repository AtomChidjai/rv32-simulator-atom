int      global_init = 42;
int      global_zero;
static int static_var  = 99;
static int static_bss;

const int ro_constant   = 0xDEAD;
const char ro_msg[]      = "hello";

void _start() {
    global_init = global_init + 1;       // 42 + 1 = 43
    global_zero = 7;
    static_var  = static_var + ro_constant; // 99 + 0xDEAD = 57004
    static_bss  = (int)ro_msg[0];           // 'h' = 0x68 = 104

    __asm__ volatile ("ebreak");
}
