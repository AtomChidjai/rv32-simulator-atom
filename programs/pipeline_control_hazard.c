volatile unsigned int branch_result;

void _start(void) {
    unsigned int value = 0;

    if (value == 0) {
        branch_result = 7;
    } else {
        branch_result = 99;
    }

    __builtin_trap();
}
