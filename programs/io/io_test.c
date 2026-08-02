#define CONSOLE_OUT (*(volatile char *)0x10000000)

void putc(char c) {
    CONSOLE_OUT = c;
}

void puts(const char *s) {
    while (*s) putc(*s++);
}

int main() {
    puts("Hello");
    return 0;
}

void _start() {
    main();
    __asm__ volatile ("ebreak");
}
