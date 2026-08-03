#define CONSOLE_OUT (*(volatile char *)0x10000000)
#define CONSOLE_IN  (*(volatile char *)0x10000004)

static void put_character(char character) { CONSOLE_OUT = character; }
static char get_character(void) { return CONSOLE_IN; }

void _start(void) {
    put_character('>');
    put_character(' ');
    char character = get_character();
    put_character(character);
    put_character('\n');
    __builtin_trap();
}
