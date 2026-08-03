/* Compile this source with RV32IC and inspect GCC's compressed output. */

volatile unsigned int compressed_result;

void _start(void) {
    unsigned int value = 10u;
    value += 2u;
    value += 5u;
    value -= 5u;
    value <<= 1u;
    compressed_result = value + 1u;
    __builtin_trap();
}
