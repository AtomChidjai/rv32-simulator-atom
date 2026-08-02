#define CONSOLE_OUT (*(volatile char *)0x10000000)
#define CONSOLE_IN  (*(volatile char *)0x10000004)

void putc(char c) { CONSOLE_OUT = c; }
char getchar() { return CONSOLE_IN; }

int main() {
    putc('>');
    putc(' ');
    char c = getchar();
    putc(c);
    putc('\n');
    return 0;
}

void _start() {
    main();
    __asm__ volatile ("ebreak");
}
