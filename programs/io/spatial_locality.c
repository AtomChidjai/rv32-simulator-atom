/* Four adjacent reads: one cold miss followed by same-block hits. */

volatile unsigned int spatial_sum;

void _start(void) {
    volatile unsigned int *words = (volatile unsigned int *)0x80000000u;

    unsigned int first = words[0];
    unsigned int second = words[1];
    unsigned int third = words[2];
    unsigned int fourth = words[3];
    spatial_sum = first + second + third + fourth;

    __builtin_trap();
}
