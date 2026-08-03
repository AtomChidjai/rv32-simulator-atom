#define CONSOLE_OUT (*(volatile char *)0x10000000u)

static void print_text(const char *text) {
    while (*text) {
        CONSOLE_OUT = *text++;
    }
}

void _start(void) {
    print_text("Hello from RISC-V!\n");
    __builtin_trap();
}
