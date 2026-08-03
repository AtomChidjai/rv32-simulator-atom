.section .text
.globl _start
.type _start, @function

_start:
    li  t0, 5
    add t1, t0, t0
    add t2, t1, t0
    nop
    nop
    nop
    nop
    ebreak

.size _start, .-_start
