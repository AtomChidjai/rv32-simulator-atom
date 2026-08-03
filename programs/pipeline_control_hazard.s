.section .text
.globl _start
.type _start, @function

_start:
    beq  zero, zero, branch_taken
    li   t0, 99

branch_taken:
    li   t0, 7
    nop
    nop
    nop
    ebreak

.size _start, .-_start
