void _start() {
    int rd;
    // ── CSR Register-Address Instructions ──
    // csrrw  — atomic Read/Write CSR
    // csrrw rd, csr, rs1   →   CSR[csr] = rs1,  rd = old CSR[csr]
    __asm__ volatile ("csrrw %0, mstatus, zero" : "=r"(rd));
    // csrrs  — atomic Read & Set bits in CSR
    // csrrs rd, csr, rs1   →   CSR[csr] |= rs1,  rd = old CSR[csr]
    __asm__ volatile ("csrrs %0, mstatus, zero" : "=r"(rd));
    // csrrc  — atomic Read & Clear bits in CSR
    // csrrc rd, csr, rs1   →   CSR[csr] &= ~rs1, rd = old CSR[csr]
    __asm__ volatile ("csrrc %0, mstatus, zero" : "=r"(rd));
    // ── CSR Immediate Instructions ──
    // csrrwi — atomic Read/Write CSR (immediate zero-extended)
    // csrrwi rd, csr, uimm5   →   CSR[csr] = uimm5, rd = old CSR[csr]
    __asm__ volatile ("csrrwi %0, mstatus, 0" : "=r"(rd));
    // csrrsi — atomic Read & Set bits in CSR (immediate zero-extended)
    // csrrsi rd, csr, uimm5   →   CSR[csr] |= uimm5, rd = old CSR[csr]
    __asm__ volatile ("csrrsi %0, mstatus, 0" : "=r"(rd));
    // csrrci — atomic Read & Clear bits in CSR (immediate zero-extended)
    // csrrci rd, csr, uimm5   →   CSR[csr] &= ~uimm5, rd = old CSR[csr]
    __asm__ volatile ("csrrci %0, mstatus, 0" : "=r"(rd));

    __asm__ volatile ("ebreak");
}
