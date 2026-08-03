.equ CONSOLE_OUT, 0x10000000
.equ CONSOLE_IN,  0x10000004

.section .text
.globl _start
.type _start, @function

_start:
    li t0, CONSOLE_OUT
    li t1, CONSOLE_IN

    li t2, '>'
    sb t2, 0(t0)
    li t2, ' '
    sb t2, 0(t0)

    lbu t2, 0(t1)
    sb  t2, 0(t0)
    li  t2, '\n'
    sb  t2, 0(t0)
    ebreak

.size _start, .-_start
