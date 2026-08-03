.section .text
.globl _start
.type _start, @function

_start:
    lui   t0, 0x1
    auipc t1, 0

    li    t2, 10
    li    s0, 7
    add   s1, t2, s0
    sub   a0, t2, s0
    mul   a1, t2, s0
    div   a2, t2, s0

    sw    s1, 0(t0)
    sb    s0, 4(t0)
    lw    a2, 0(t0)
    lb    a3, 4(t0)

    beq   t2, t2, 1f
    li    a4, 99
1:
    bne   t2, s0, 2f
    li    a4, 88
2:
    call  demo_function

    csrrw a5, mscratch, t2
    csrrs a6, mscratch, zero
    ebreak

demo_function:
    li    a7, 42
    ret

.size _start, .-_start
