/* C tour: arithmetic, memory, branches, and a real function call. */

typedef unsigned int u32;

static __attribute__((noinline)) u32 combine(u32 left, u32 right) {
    return (left + right) * 2u;
}

void _start(void) {
    volatile u32 *memory = (volatile u32 *)0x1000u;
    u32 left = 10u;
    u32 right = 7u;

    memory[0] = left + right;
    memory[1] = left - right;
    memory[2] = left * right;
    memory[3] = left / right;

    if (left != right) {
        memory[4] = combine(memory[0], memory[1]);
    }

    __builtin_trap();
}
