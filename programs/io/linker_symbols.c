/* Linker-symbol demo. */
extern const unsigned int __stack_top;
extern const unsigned int _end;
extern const unsigned int __global_pointer$;
extern const unsigned int __bss_start;
extern const unsigned int __bss_end;

void _start(void) {
    __asm__ volatile(
        "la a0, __stack_top\n\t"
        "la a1, _end\n\t"
        "la a2, __global_pointer$\n\t"
        "la a3, __bss_start\n\t"
        "la a4, __bss_end\n\t"
        "ebreak\n\t"
    );
}
