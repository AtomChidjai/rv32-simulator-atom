#define CONSOLE_OUT (*(volatile char *)0x10000000u)

volatile unsigned int values[] = {4, 1, 3, 2};

static inline __attribute__((always_inline)) void print_character(char character) {
    CONSOLE_OUT = character;
}

__attribute__((optimize("O1")))
void _start(void) {
    const unsigned int count = sizeof(values) / sizeof(values[0]);

    for (unsigned int end = count; end > 1; --end) {
        for (unsigned int index = 0; index + 1 < end; ++index) {
            if (values[index] > values[index + 1]) {
                unsigned int temporary = values[index];
                values[index] = values[index + 1];
                values[index + 1] = temporary;
            }
        }
    }

    for (unsigned int index = 0; index < count; ++index) {
        print_character((char)('0' + values[index]));
        print_character(index + 1 == count ? '\n' : ' ');
    }

    __asm__ volatile ("ebreak");
}
