#include "op_test.h"

#define MAX_TESTS 512
static struct { const char *name; op_test_fn fn; } g_tests[MAX_TESTS];
static int g_count;
static int g_failed_in_current;
static int g_failures;
int op_test_assertions;

void op_test_register(const char *name, op_test_fn fn)
{
    if (g_count < MAX_TESTS) {
        g_tests[g_count].name = name;
        g_tests[g_count].fn = fn;
        g_count++;
    }
}

void op_test_fail(const char *file, int line, const char *expr)
{
    g_failed_in_current++;
    printf("    FAIL %s:%d: %s\n", file, line, expr);
}

int main(void)
{
    int passed = 0;
    for (int i = 0; i < g_count; i++) {
        g_failed_in_current = 0;
        g_tests[i].fn();
        if (g_failed_in_current) {
            g_failures++;
            printf("[FAIL] %s\n", g_tests[i].name);
        } else {
            passed++;
        }
    }
    printf("%d tests, %d passed, %d failed, %d assertions\n", g_count, passed, g_failures, op_test_assertions);
    return g_failures ? 1 : 0;
}
