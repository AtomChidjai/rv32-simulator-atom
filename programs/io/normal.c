int counter = 0;
int result = 0;

int add(int a, int b) {
    return a + b;
}

int multiply_by_shift(int x, int n) {
    int res = 0;
    for (int i = 0; i < n; i++) {
        res = add(res, x);
    }
    return res;
}

void _start() {
    counter = 10;
    result = add(counter, 5);            // result = 15
    result = multiply_by_shift(result, 3); // result = 45

    __asm__ volatile ("ebreak");
}
