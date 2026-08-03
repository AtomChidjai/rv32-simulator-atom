.equ CONSOLE_OUT, 0x10000000

.section .text
.globl _start
.type _start, @function

_start:
    li   t0, CONSOLE_OUT
    la   t1, message

1:
    lbu  t2, 0(t1)
    beqz t2, 2f
    sb   t2, 0(t0)
    addi t1, t1, 1
    j    1b

2:
    ebreak

.size _start, .-_start

.section .rodata
message:
    .asciz "Hello from RISC-V!\n"
