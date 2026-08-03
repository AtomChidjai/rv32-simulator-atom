volatile unsigned int pipeline_result;

void _start(void) {
    unsigned int first = 5u;
    unsigned int second = first + first;
    pipeline_result = second + first;
    __builtin_trap();
}
