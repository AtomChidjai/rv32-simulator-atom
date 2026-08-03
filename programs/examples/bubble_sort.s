.equ CONSOLE_OUT, 0x10000000

.section .text
.globl _start
.type _start, @function

_start:
    la s0, values
    li s1, 4
    mv t0, s1

sort_outer:
    li   t1, 0
    addi t2, t0, -1

sort_inner:
    bgeu t1, t2, sort_next_pass
    slli t3, t1, 2
    add  t4, s0, t3
    lw   t5, 0(t4)
    lw   t6, 4(t4)
    bleu t5, t6, no_swap
    sw   t6, 0(t4)
    sw   t5, 4(t4)

no_swap:
    addi t1, t1, 1
    j    sort_inner

sort_next_pass:
    addi t0, t0, -1
    li   t1, 1
    bgtu t0, t1, sort_outer

    li t0, 0
    li t4, CONSOLE_OUT

print_loop:
    slli t1, t0, 2
    add  t2, s0, t1
    lw   t3, 0(t2)
    addi t3, t3, '0'
    sb   t3, 0(t4)
    addi t0, t0, 1
    beq  t0, s1, print_newline
    li   t3, ' '
    sb   t3, 0(t4)
    j    print_loop

print_newline:
    li t3, '\n'
    sb t3, 0(t4)
    ebreak

.size _start, .-_start

.section .data
.align 2
values:
    .word 4, 1, 3, 2
