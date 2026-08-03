.section .text
.globl _start
.type _start, @function

_start:
    li t0, 0x80000000

    lw t1, 0(t0)
    lw t2, 4(t0)
    lw t3, 8(t0)
    lw t4, 12(t0)

    add t5, t1, t2
    add t5, t5, t3
    add t5, t5, t4
    ebreak

.size _start, .-_start
