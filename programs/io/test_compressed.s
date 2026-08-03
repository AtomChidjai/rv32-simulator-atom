.option rvc
.section .text
.globl _start
.type _start, @function

_start:
    c.li    a0, 10
    c.li    a1, 5
    c.addi  a0, 2
    c.add   a0, a1
    c.sub   a0, a1
    c.slli  a0, 1
    c.addi  a0, 1
    c.ebreak

.size _start, .-_start
