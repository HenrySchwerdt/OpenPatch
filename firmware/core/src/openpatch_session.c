#include <string.h>

#include "op/openpatch_proto.h"

void op_session_init(op_session_t *s, const op_ccm_ops_t *ccm, const uint8_t salt[4], bool allow_plaintext)
{
    memset(s, 0, sizeof *s);
    s->ccm = ccm;
    s->allow_plaintext = allow_plaintext;
    memcpy(s->salt, salt, 4);
}

void op_session_nonce(const op_session_t *s, bool response, uint16_t seq, uint8_t nonce[OP_CCM_NONCE_LEN])
{
    memset(nonce, 0, OP_CCM_NONCE_LEN);
    memcpy(nonce, s->salt, 4);
    nonce[4] = response ? 1 : 0;
    nonce[5] = (uint8_t)seq;
    nonce[6] = (uint8_t)(seq >> 8);
}

int op_session_open(op_session_t *s, const uint8_t *in, size_t len, op_frame_t *out, uint8_t *plain,
                    size_t plain_cap)
{
    int rc = op_frame_decode(in, len, out);
    if (rc < 0) return rc;
    bool is_response = (out->flags & OP_FLAG_RESPONSE) != 0;

    if (out->flags & OP_FLAG_ENCRYPTED) {
        if (!s->ccm || !s->ccm->decrypt) return -OP_ERR_AUTH;
        if (out->payload_len < OP_CCM_TAG_LEN) return -OP_ERR_FRAME;
        size_t ct_len = out->payload_len - OP_CCM_TAG_LEN;
        if (ct_len > plain_cap) return -OP_ERR_TOO_LARGE;
        uint8_t nonce[OP_CCM_NONCE_LEN];
        op_session_nonce(s, is_response, out->seq, nonce);
        if (s->ccm->decrypt(s->ccm->ctx, nonce, in, OP_FRAME_HEADER, out->payload, ct_len,
                            out->payload + ct_len, plain) != 0)
            return -OP_ERR_AUTH;
        out->payload = plain;
        out->payload_len = (uint16_t)ct_len;
    } else if (!s->allow_plaintext) {
        return -OP_ERR_AUTH;
    }

    if (!is_response) {
        if (s->rx_seen && out->seq <= s->last_rx_seq) return -OP_ERR_REPLAY;
        if (out->seq > OP_SEQ_MAX) return -OP_ERR_SESSION;
        s->rx_seen = true;
        s->last_rx_seq = out->seq;
        if (s->ccm && s->ccm->on_seq_accepted) s->ccm->on_seq_accepted(s->ccm->ctx, out->seq);
    }
    return 0;
}

int op_session_seal(const op_session_t *s, bool response, uint8_t type, uint16_t seq, bool encrypt,
                    const uint8_t *payload, size_t plen, uint8_t *out, size_t cap)
{
    if (seq > OP_SEQ_MAX) return -OP_ERR_SESSION;
    if (plen > 0 && !payload) return -OP_ERR_BAD_ARG;
    uint8_t flags = response ? OP_FLAG_RESPONSE : 0;
    if (!encrypt) {
        op_frame_t f = {OP_PROTO_VERSION, type, flags, seq, payload, (uint16_t)plen};
        return op_frame_encode(&f, out, cap);
    }
    if (!s->ccm || !s->ccm->encrypt) return -OP_ERR_AUTH;
    size_t body = plen + OP_CCM_TAG_LEN;
    size_t total = OP_FRAME_HEADER + body + OP_FRAME_CRC;
    if (total > OP_FRAME_MAX || total > cap) return -OP_ERR_TOO_LARGE;
    out[0] = OP_PROTO_VERSION;
    out[1] = type;
    out[2] = (uint8_t)(flags | OP_FLAG_ENCRYPTED);
    out[3] = (uint8_t)seq;
    out[4] = (uint8_t)(seq >> 8);
    out[5] = (uint8_t)body;
    out[6] = (uint8_t)(body >> 8);
    uint8_t nonce[OP_CCM_NONCE_LEN];
    op_session_nonce(s, response, seq, nonce);
    if (s->ccm->encrypt(s->ccm->ctx, nonce, out, OP_FRAME_HEADER, payload, plen, out + OP_FRAME_HEADER,
                        out + OP_FRAME_HEADER + plen) != 0)
        return -OP_ERR_AUTH;
    uint16_t crc = op_crc16(out, total - OP_FRAME_CRC);
    out[total - 2] = (uint8_t)crc;
    out[total - 1] = (uint8_t)(crc >> 8);
    return (int)total;
}
