#include <string.h>

#include "op/openpatch_proto.h"

uint16_t op_crc16(const uint8_t *data, size_t len)
{
    uint32_t crc = 0xFFFFu;
    for (size_t i = 0; i < len; i++) {
        crc ^= (uint32_t)data[i] << 8;
        for (int b = 0; b < 8; b++) crc = (crc & 0x8000u) ? ((crc << 1) ^ 0x1021u) & 0xFFFFu : (crc << 1) & 0xFFFFu;
    }
    return (uint16_t)crc;
}

static void put_le16(uint8_t *p, uint16_t v)
{
    p[0] = (uint8_t)v;
    p[1] = (uint8_t)(v >> 8);
}
static uint16_t get_le16(const uint8_t *p) { return (uint16_t)(p[0] | (p[1] << 8)); }

int op_frame_encode(const op_frame_t *f, uint8_t *out, size_t cap)
{
    if (!f || !out || (f->payload_len > 0 && !f->payload)) return -OP_ERR_BAD_ARG;
    size_t total = OP_FRAME_HEADER + f->payload_len + OP_FRAME_CRC;
    if (total > OP_FRAME_MAX || total > cap) return -OP_ERR_TOO_LARGE;
    out[0] = f->version;
    out[1] = f->type;
    out[2] = f->flags;
    put_le16(out + 3, f->seq);
    put_le16(out + 5, f->payload_len);
    if (f->payload_len) memcpy(out + OP_FRAME_HEADER, f->payload, f->payload_len);
    put_le16(out + total - OP_FRAME_CRC, op_crc16(out, total - OP_FRAME_CRC));
    return (int)total;
}

int op_frame_decode(const uint8_t *in, size_t len, op_frame_t *out)
{
    if (!in || !out) return -OP_ERR_BAD_ARG;
    if (len < OP_FRAME_HEADER + OP_FRAME_CRC || len > OP_FRAME_MAX) return -OP_ERR_FRAME;
    uint16_t plen = get_le16(in + 5);
    if ((size_t)OP_FRAME_HEADER + plen + OP_FRAME_CRC != len) return -OP_ERR_FRAME;
    if (op_crc16(in, len - OP_FRAME_CRC) != get_le16(in + len - OP_FRAME_CRC)) return -OP_ERR_CRC;
    if (in[0] != OP_PROTO_VERSION) return -OP_ERR_VERSION;
    out->version = in[0];
    out->type = in[1];
    out->flags = in[2];
    out->seq = get_le16(in + 3);
    out->payload = in + OP_FRAME_HEADER;
    out->payload_len = plen;
    return 0;
}

/* ---- TLV ------------------------------------------------------------------ */
void op_tlv_w_init(op_tlv_w_t *w, uint8_t *buf, size_t cap)
{
    w->buf = buf;
    w->cap = cap;
    w->len = 0;
    w->overflow = false;
}

void op_tlv_put(op_tlv_w_t *w, uint8_t tag, const void *v, uint8_t vlen)
{
    if (w->overflow) return;
    if (w->len + 2u + vlen > w->cap) {
        w->overflow = true;
        return;
    }
    w->buf[w->len++] = tag;
    w->buf[w->len++] = vlen;
    if (vlen) memcpy(w->buf + w->len, v, vlen);
    w->len += vlen;
}

void op_tlv_put_u8(op_tlv_w_t *w, uint8_t tag, uint8_t v) { op_tlv_put(w, tag, &v, 1); }

void op_tlv_put_u16(op_tlv_w_t *w, uint8_t tag, uint16_t v)
{
    uint8_t b[2];
    put_le16(b, v);
    op_tlv_put(w, tag, b, 2);
}

void op_tlv_put_u32(op_tlv_w_t *w, uint8_t tag, uint32_t v)
{
    uint8_t b[4] = {(uint8_t)v, (uint8_t)(v >> 8), (uint8_t)(v >> 16), (uint8_t)(v >> 24)};
    op_tlv_put(w, tag, b, 4);
}

void op_tlv_r_init(op_tlv_r_t *r, const uint8_t *p, size_t len)
{
    r->p = p;
    r->len = p ? len : 0;
    r->pos = 0;
    r->error = false;
}

bool op_tlv_next(op_tlv_r_t *r, uint8_t *tag, const uint8_t **v, uint8_t *vlen)
{
    if (r->error || r->pos >= r->len) return false;
    if (r->len - r->pos < 2) {
        r->error = true;
        return false;
    }
    uint8_t t = r->p[r->pos];
    uint8_t l = r->p[r->pos + 1];
    if ((size_t)l > r->len - r->pos - 2) {
        r->error = true;
        return false;
    }
    *tag = t;
    *vlen = l;
    *v = r->p + r->pos + 2;
    r->pos += 2u + l;
    return true;
}
