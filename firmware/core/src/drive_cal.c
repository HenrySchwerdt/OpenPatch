#include "op/drive_cal.h"

#include <string.h>

static void wr16(uint8_t *b, uint16_t v)
{
    b[0] = (uint8_t)v;
    b[1] = (uint8_t)(v >> 8);
}

static void wr32(uint8_t *b, uint32_t v)
{
    wr16(b, (uint16_t)v);
    wr16(b + 2, (uint16_t)(v >> 16));
}

static uint32_t crc32_update(uint32_t crc, const uint8_t *p, size_t n)
{
    crc = ~crc;
    for (size_t i = 0; i < n; i++) {
        crc ^= p[i];
        for (int k = 0; k < 8; k++) crc = (crc >> 1) ^ (0xEDB88320u & (uint32_t)-(int32_t)(crc & 1u));
    }
    return ~crc;
}

uint32_t op_drive_cal_crc(const op_drive_cal_t *c)
{
    uint8_t b[16];
    wr32(b, c->magic);
    wr16(b + 4, c->drive_id);
    wr16(b + 6, c->steps_per_rev);
    wr16(b + 8, c->gear_ratio_x100);
    wr16(b + 10, c->reserved);
    wr32(b + 12, c->micro_u_per_step);
    return crc32_update(0, b, sizeof b);
}

op_err_t op_drive_cal_preset(op_drive_id_t id, op_drive_cal_t *out)
{
    if (!out) return OP_ERR_BAD_ARG;
    memset(out, 0, sizeof *out);
    out->magic = OP_DRIVE_CAL_MAGIC;
    out->drive_id = (uint16_t)id;
    out->steps_per_rev = 20;
    switch (id) {
    case OP_DRIVE_ZWBPD006006_5_1:
        out->gear_ratio_x100 = 500;
        out->micro_u_per_step = OP_DRIVE_ZWBPD006006_UU_PER_STEP;
        break;
    case OP_DRIVE_FAULHABER_16_1:
        out->gear_ratio_x100 = 1600;
        out->micro_u_per_step = OP_DRIVE_FAULHABER_16_1_UU_PER_STEP;
        break;
    default:
        memset(out, 0, sizeof *out);
        return OP_ERR_BAD_ARG;
    }
    out->crc32 = op_drive_cal_crc(out);
    return OP_OK;
}

op_err_t op_drive_cal_validate(const op_drive_cal_t *c)
{
    if (!c) return OP_ERR_NOT_FOUND;
    if (c->magic != OP_DRIVE_CAL_MAGIC) return OP_ERR_NOT_FOUND;
    if (c->crc32 != op_drive_cal_crc(c)) return OP_ERR_CRC;
    if (c->reserved != 0) return OP_ERR_BAD_ARG;
    if (c->micro_u_per_step < OP_CAL_UU_MIN || c->micro_u_per_step > OP_CAL_UU_MAX) return OP_ERR_LIMIT;
    op_drive_cal_t ref;
    if (op_drive_cal_preset((op_drive_id_t)c->drive_id, &ref) != OP_OK) return OP_ERR_BAD_ARG;
    return memcmp(&ref, c, sizeof ref) == 0 ? OP_OK : OP_ERR_BAD_ARG;
}

uint32_t op_drive_cal_steps_per_spindle_rev(const op_drive_cal_t *c)
{
    if (op_drive_cal_validate(c) != OP_OK) return 0;
    return (uint32_t)c->steps_per_rev * c->gear_ratio_x100 / 100u;
}
