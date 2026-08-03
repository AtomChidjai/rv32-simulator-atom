.equ MTIME_LO,    0x10000010
.equ MTIMECMP_LO, 0x10000018
.equ MTIMECMP_HI, 0x1000001c

.section .text
.globl _start
.type _start, @function

_start:
    la   t0, timer_interrupt_handler
    csrw mtvec, t0

    li   t0, MTIME_LO
    lw   t1, 0(t0)
    addi t1, t1, 200
    li   t0, MTIMECMP_LO
    sw   t1, 0(t0)
    li   t0, MTIMECMP_HI
    sw   zero, 0(t0)

    li   t0, (1 << 7)
    csrs mie, t0
    li   t0, (1 << 3)
    csrs mstatus, t0

    la t0, timer_interrupt_seen
1:
    lw   t1, 0(t0)
    beqz t1, 1b
    ebreak

.size _start, .-_start

.type timer_interrupt_handler, @function
timer_interrupt_handler:
    addi sp, sp, -16
    sw   t0, 0(sp)
    sw   t1, 4(sp)
    sw   t2, 8(sp)

    csrr t0, mcause
    li   t1, 0x80000007
    bne  t0, t1, 2f

    li   t0, MTIME_LO
    lw   t1, 0(t0)
    li   t2, 0x1000
    add  t1, t1, t2
    li   t0, MTIMECMP_LO
    sw   t1, 0(t0)
    li   t0, MTIMECMP_HI
    sw   zero, 0(t0)

    la   t0, timer_interrupt_seen
    li   t1, 1
    sw   t1, 0(t0)

2:
    lw   t0, 0(sp)
    lw   t1, 4(sp)
    lw   t2, 8(sp)
    addi sp, sp, 16
    mret

.size timer_interrupt_handler, .-timer_interrupt_handler

.section .bss
.align 2
timer_interrupt_seen:
    .word 0
