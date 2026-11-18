#include "op/openpatch_proto.h"
#include "op_test.h"

#include "fake_ccm.h"

#define g_ccm fake_ccm_ops
#define g_ctx fake_ccm_ctx

static const uint8_t SALT[4] = {1, 2, 3, 4};

static int make_cmd(const op_session_t *s, uint16_t seq, bool enc, uint8_t *out, size_t cap)
{
    static const uint8_t payload[] = {OP_TAG_AMOUNT_MU, 4, 0xD0, 0x07, 0, 0};
    return op_session_seal(s, false, OP_CMD_BOLUS, seq, enc, payload, sizeof payload, out, cap);
}

TEST(session_nonce_layout)
{
    op_session_t s;
    op_session_init(&s, &g_ccm, SALT, false);
    uint8_t n[13];
    op_session_nonce(&s, true, 0x0A0B, n);
    static const uint8_t expect[13] = {1, 2, 3, 4, 1, 0x0B, 0x0A, 0, 0, 0, 0, 0, 0};
    CHECK_MEM(n, expect, 13);
    op_session_nonce(&s, false, 1, n);
    CHECK_EQ(n[4], 0);
}

TEST(session_plaintext_accepted_only_when_allowed)
{
    op_session_t s;
    uint8_t buf[64], plain[64];
    op_frame_t f;
    op_session_init(&s, NULL, SALT, true);
    int n = make_cmd(&s, 1, false, buf, sizeof buf);
    CHECK(n > 0);
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), 0);
    CHECK_EQ(f.type, OP_CMD_BOLUS);

    op_session_init(&s, &g_ccm, SALT, false); /* production config */
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), -OP_ERR_AUTH);
    CHECK(!s.rx_seen);
}

TEST(session_encrypted_roundtrip_and_hook)
{
    op_session_t s;
    uint8_t buf[64], plain[64];
    op_frame_t f;
    memset(&g_ctx, 0, sizeof g_ctx);
    op_session_init(&s, &g_ccm, SALT, false);
    int n = make_cmd(&s, 7, true, buf, sizeof buf);
    CHECK(n > 0);
    CHECK(buf[2] & OP_FLAG_ENCRYPTED);
    CHECK(memcmp(buf + OP_FRAME_HEADER, (const uint8_t[]){OP_TAG_AMOUNT_MU, 4}, 2) != 0); /* really scrambled */
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), 0);
    CHECK_EQ(f.payload_len, 6);
    CHECK_EQ(f.payload[0], OP_TAG_AMOUNT_MU);
    CHECK_EQ(g_ctx.accepted_calls, 1);
    CHECK_EQ(g_ctx.last_seq, 7);
    op_cmd_t c;
    CHECK_EQ(op_cmd_decode(f.type, f.seq, f.payload, f.payload_len, &c), 0);
    CHECK_EQ(c.u.bolus.amount_mu, 2000);
}

TEST(session_tampering_is_rejected_without_advancing_state)
{
    op_session_t s;
    uint8_t buf[64], copy[64], plain[64];
    op_frame_t f;
    memset(&g_ctx, 0, sizeof g_ctx);
    op_session_init(&s, &g_ccm, SALT, false);
    int n = make_cmd(&s, 3, true, buf, sizeof buf);
    /* flip a ciphertext bit, repair the CRC so only the CCM tag can catch it */
    memcpy(copy, buf, (size_t)n);
    copy[OP_FRAME_HEADER] ^= 1;
    uint16_t crc = op_crc16(copy, (size_t)n - 2);
    copy[n - 2] = (uint8_t)crc;
    copy[n - 1] = (uint8_t)(crc >> 8);
    CHECK_EQ(op_session_open(&s, copy, (size_t)n, &f, plain, sizeof plain), -OP_ERR_AUTH);
    CHECK(!s.rx_seen);
    CHECK_EQ(g_ctx.accepted_calls, 0);
    /* header tamper (type): AAD covers the header */
    memcpy(copy, buf, (size_t)n);
    copy[1] = OP_CMD_SUSPEND;
    crc = op_crc16(copy, (size_t)n - 2);
    copy[n - 2] = (uint8_t)crc;
    copy[n - 1] = (uint8_t)(crc >> 8);
    CHECK_EQ(op_session_open(&s, copy, (size_t)n, &f, plain, sizeof plain), -OP_ERR_AUTH);
    /* the genuine frame still works afterwards */
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), 0);
}

TEST(session_replay_protection)
{
    op_session_t s;
    uint8_t b1[64], b2[64], b3[64], plain[64];
    op_frame_t f;
    op_session_init(&s, &g_ccm, SALT, false);
    int n1 = make_cmd(&s, 5, true, b1, sizeof b1);
    int n2 = make_cmd(&s, 6, true, b2, sizeof b2);
    int n3 = make_cmd(&s, 4, true, b3, sizeof b3);
    CHECK_EQ(op_session_open(&s, b1, (size_t)n1, &f, plain, sizeof plain), 0);
    CHECK_EQ(op_session_open(&s, b1, (size_t)n1, &f, plain, sizeof plain), -OP_ERR_REPLAY); /* exact replay */
    CHECK_EQ(op_session_open(&s, b3, (size_t)n3, &f, plain, sizeof plain), -OP_ERR_REPLAY); /* older */
    CHECK_EQ(op_session_open(&s, b2, (size_t)n2, &f, plain, sizeof plain), 0);
    CHECK_EQ(s.last_rx_seq, 6);
}

TEST(session_first_sequence_may_be_zero_and_gaps_are_allowed)
{
    op_session_t s;
    uint8_t buf[64], plain[64];
    op_frame_t f;
    op_session_init(&s, NULL, SALT, true);
    int n = make_cmd(&s, 0, false, buf, sizeof buf);
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), 0);
    n = make_cmd(&s, 1000, false, buf, sizeof buf);
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), 0);
}

TEST(session_exhausted_sequence_space_requires_rekey)
{
    op_session_t s;
    uint8_t buf[64], plain[64];
    op_frame_t f;
    op_session_init(&s, NULL, SALT, true);
    op_frame_t raw = {OP_PROTO_VERSION, OP_CMD_BOLUS, 0, 0xFFFF, NULL, 0};
    int n = op_frame_encode(&raw, buf, sizeof buf);
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), -OP_ERR_SESSION);
    n = make_cmd(&s, OP_SEQ_MAX, false, buf, sizeof buf);
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), 0);
    CHECK_EQ(op_session_seal(&s, false, OP_CMD_BOLUS, 0xFFFF, true, NULL, 0, buf, sizeof buf), -OP_ERR_SESSION);
}

TEST(session_rejects_garbage_and_encrypted_without_crypto)
{
    op_session_t s;
    uint8_t buf[64], plain[64], bad[9] = {0};
    op_frame_t f;
    op_session_init(&s, NULL, SALT, true);
    CHECK_EQ(op_session_open(&s, bad, sizeof bad, &f, plain, sizeof plain), -OP_ERR_CRC);
    op_session_t enc;
    op_session_init(&enc, &g_ccm, SALT, false);
    int n = make_cmd(&enc, 1, true, buf, sizeof buf);
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), -OP_ERR_AUTH); /* ccm == NULL */
    CHECK_EQ(op_session_open(&enc, buf, 4, &f, plain, sizeof plain), -OP_ERR_FRAME);
    CHECK_EQ(op_session_open(&enc, buf, (size_t)n, &f, plain, 3), -OP_ERR_TOO_LARGE);
}

TEST(session_rejects_encrypted_payload_shorter_than_tag)
{
    op_session_t s;
    op_session_init(&s, &g_ccm, SALT, false);
    op_frame_t raw = {OP_PROTO_VERSION, OP_CMD_BOLUS, OP_FLAG_ENCRYPTED, 1, (const uint8_t *)"abc", 3};
    uint8_t buf[32], plain[32];
    op_frame_t f;
    int n = op_frame_encode(&raw, buf, sizeof buf);
    CHECK_EQ(op_session_open(&s, buf, (size_t)n, &f, plain, sizeof plain), -OP_ERR_FRAME);
}

TEST(session_seal_cannot_encrypt_without_crypto)
{
    op_session_t s;
    uint8_t buf[64];
    op_session_init(&s, NULL, SALT, true);
    CHECK_EQ(make_cmd(&s, 1, true, buf, sizeof buf), -OP_ERR_AUTH);
    CHECK_EQ(op_session_seal(&s, true, 0x85, 1, false, NULL, 1, buf, sizeof buf), -OP_ERR_BAD_ARG);
}

TEST(session_seal_sets_response_flag_and_respects_capacity)
{
    op_session_t s;
    uint8_t buf[64], small[10];
    op_frame_t f;
    op_session_init(&s, &g_ccm, SALT, false);
    int n = op_session_seal(&s, true, OP_CMD_BOLUS | OP_RSP_BIT, 9, true, (const uint8_t[]){1, 1, 0}, 3, buf, sizeof buf);
    CHECK(n > 0);
    CHECK_EQ(op_frame_decode(buf, (size_t)n, &f), 0);
    CHECK(f.flags & OP_FLAG_RESPONSE);
    CHECK(f.flags & OP_FLAG_ENCRYPTED);
    CHECK_EQ(f.payload_len, 3 + OP_CCM_TAG_LEN);
    CHECK_EQ(op_session_seal(&s, true, 0x85, 9, true, (const uint8_t[]){1, 1, 0}, 3, small, sizeof small), -OP_ERR_TOO_LARGE);
}

TEST(session_seal_fails_when_ccm_backend_fails)
{
    static const op_ccm_ops_t bad = {NULL, NULL, NULL, NULL};
    op_session_t s;
    uint8_t buf[64];
    op_session_init(&s, &bad, SALT, false);
    CHECK_EQ(op_session_seal(&s, true, 0x85, 1, true, NULL, 0, buf, sizeof buf), -OP_ERR_AUTH);
}
