#include "fake_ccm.h"
#include <string.h>

/* TEST-ONLY fake "CCM": XOR keystream + 8-byte FNV-style tag. Not secure. */
static void keystream_xor(const uint8_t nonce[13], const uint8_t *in, size_t n, uint8_t *out)
{
    for (size_t i = 0; i < n; i++) out[i] = in[i] ^ (uint8_t)(nonce[i % 13] + 0x5A + i);
}
static void tag_of(const uint8_t nonce[13], const uint8_t *aad, size_t al, const uint8_t *ct, size_t n, uint8_t tag[8])
{
    uint64_t h = 1469598103934665603ull;
    for (int i = 0; i < 13; i++) h = (h ^ nonce[i]) * 1099511628211ull;
    for (size_t i = 0; i < al; i++) h = (h ^ aad[i]) * 1099511628211ull;
    for (size_t i = 0; i < n; i++) h = (h ^ ct[i]) * 1099511628211ull;
    for (int i = 0; i < 8; i++) tag[i] = (uint8_t)(h >> (8 * i));
}
static int f_enc(void *c, const uint8_t nonce[13], const uint8_t *aad, size_t al, const uint8_t *pt, size_t n,
                 uint8_t *ct, uint8_t tag[8])
{
    (void)c;
    keystream_xor(nonce, pt, n, ct);
    tag_of(nonce, aad, al, ct, n, tag);
    return 0;
}
static int f_dec(void *c, const uint8_t nonce[13], const uint8_t *aad, size_t al, const uint8_t *ct, size_t n,
                 const uint8_t tag[8], uint8_t *pt)
{
    (void)c;
    uint8_t expect[8];
    tag_of(nonce, aad, al, ct, n, expect);
    if (memcmp(expect, tag, 8) != 0) return -1;
    keystream_xor(nonce, ct, n, pt);
    return 0;
}
static void f_seq(void *c, uint16_t seq)
{
    fake_ccm_ctx_t *x = c;
    x->accepted_calls++;
    x->last_seq = seq;
}


fake_ccm_ctx_t fake_ccm_ctx;
const op_ccm_ops_t fake_ccm_ops = {&fake_ccm_ctx, f_enc, f_dec, f_seq};
