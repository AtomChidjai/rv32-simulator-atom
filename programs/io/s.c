// ==========================================
// 1. SMALL DATA / BSS (ขนาด <= 8 bytes)
// ==========================================
int        global_init = 42;        // ไปที่ .sdata (ขนาด 4 ไบต์)
int        global_zero;             // ไปที่ .sbss  (ขนาด 4 ไบต์)
static int static_var  = 99;        // ไปที่ .sdata (ขนาด 4 ไบต์)
static int static_bss;              // ไปที่ .sbss  (ขนาด 4 ไบต์)

// ==========================================
// 2. LARGE DATA / BSS (ขนาด > 8 bytes)
// ==========================================
// อาเรย์ 10 ช่อง มีค่าเริ่มต้น (ขนาด 40 ไบต์) -> ไปที่ .data
int large_data_array[10] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};

// อาเรย์ 100 ช่อง ไม่มีค่าเริ่มต้น (ขนาด 400 ไบต์) -> ไปที่ .bss
int large_bss_array[100];

// ==========================================
// 3. READ-ONLY DATA (ค่าคงที่)
// ==========================================
const int  ro_constant  = 0xDEAD;   // ไปที่ .rodata
const char ro_msg[]     = "hello";  // ไปที่ .rodata

// ==========================================
// 4. TEXT (คำสั่งโปรแกรม)
// ==========================================
void _start() {                     // ไปที่ .text
    global_init = global_init + 1;       // 42 + 1 = 43
    global_zero = 7;
    static_var  = static_var + ro_constant;
    static_bss  = (int)ro_msg[0];        // 'h' = 0x68 = 104

    // ดึงค่าจาก .data มาคำนวณแล้วเก็บลง .bss
    // (บังคับให้ Compiler ต้องใช้งานทั้ง 2 Section นี้)
    large_bss_array[0] = large_data_array[0] + global_init;

    // คำสั่งหยุดการทำงานจำลอง
    __asm__ volatile ("ebreak");
}
