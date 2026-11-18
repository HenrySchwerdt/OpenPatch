/*
 * Minimal self-contained test harness (no network dependencies).
 * TEST(name) { ... } registers automatically via a constructor.
 */
#ifndef OP_TEST_H
#define OP_TEST_H

#include <inttypes.h>
#include <stdio.h>
#include <string.h>

typedef void (*op_test_fn)(void);
void op_test_register(const char *name, op_test_fn fn);
void op_test_fail(const char *file, int line, const char *expr);
extern int op_test_assertions;

#define TEST(name)                                                        \
    static void name(void);                                               \
    __attribute__((constructor)) static void name##_reg(void)             \
    {                                                                     \
        op_test_register(#name, name);                                    \
    }                                                                     \
    static void name(void)

#define CHECK(cond)                                                       \
    do {                                                                  \
        op_test_assertions++;                                             \
        if (!(cond)) op_test_fail(__FILE__, __LINE__, #cond);             \
    } while (0)

#define CHECK_EQ(a, b)                                                    \
    do {                                                                  \
        long long _a = (long long)(a), _b = (long long)(b);               \
        op_test_assertions++;                                             \
        if (_a != _b) {                                                   \
            char _m[160];                                                 \
            snprintf(_m, sizeof _m, "%s == %s (%lld vs %lld)", #a, #b, _a, _b); \
            op_test_fail(__FILE__, __LINE__, _m);                         \
        }                                                                 \
    } while (0)

#define CHECK_MEM(a, b, n) CHECK(memcmp((a), (b), (n)) == 0)

#endif
