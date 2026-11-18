#include "op/openpatch_proto.h"
#include "op_test.h"

/* ---- CRC ---------------------------------------------------------------- */
TEST(crc16_matches_ccitt_false_check_value)
{
    CHECK_EQ(op_crc16((const uint8_t *)"123456789", 9), 0x29B1);
    CHECK_EQ(op_crc16(NULL, 0), 0xFFFF);
}

/* ---- frame ---------------------------------------------------------------- */
TEST(frame_golden_get_status)
{
    static const uint8_t golden[] = {0x01, 0x01, 0x00, 0x01, 0x00, 0x00, 0x00, 0xBB, 0x7A};
    op_frame_t f = {OP_PROTO_VERSION, OP_CMD_GET_STATUS, 0, 1, NULL, 0};
    uint8_t out[32];
    int n = op_frame_encode(&f, out, sizeof out);
    CHECK_EQ(n, sizeof golden);
    CHECK_MEM(out, golden, sizeof golden);
}

TEST(frame_golden_bolus_decodes)
{
    static const uint8_t golden[] = {0x01, 0x05, 0x00, 0x02, 0x01, 0x06, 0x00, 0x05,
                                     0x04, 0xD0, 0x07, 0x00, 0x00, 0x38, 0x31};
    op_frame_t f;
    CHECK_EQ(op_frame_decode(golden, sizeof golden, &f), 0);
    CHECK_EQ(f.type, OP_CMD_BOLUS);
    CHECK_EQ(f.seq, 0x0102);
    CHECK_EQ(f.payload_len, 6);
    op_cmd_t c;
    CHECK_EQ(op_cmd_decode(f.type, f.seq, f.payload, f.payload_len, &c), 0);
    CHECK_EQ(c.u.bolus.amount_mu, 2000);
}

TEST(frame_roundtrip_with_payload)
{
    uint8_t payload[20];
    for (int i = 0; i < 20; i++) payload[i] = (uint8_t)(i * 7);
    op_frame_t f = {OP_PROTO_VERSION, 0x42, OP_FLAG_RESPONSE, 0xBEEF, payload, 20};
    uint8_t buf[64];
    int n = op_frame_encode(&f, buf, sizeof buf);
    CHECK_EQ(n, OP_FRAME_HEADER + 20 + OP_FRAME_CRC);
    op_frame_t d;
    CHECK_EQ(op_frame_decode(buf, (size_t)n, &d), 0);
    CHECK_EQ(d.version, OP_PROTO_VERSION);
    CHECK_EQ(d.type, 0x42);
    CHECK_EQ(d.flags, OP_FLAG_RESPONSE);
    CHECK_EQ(d.seq, 0xBEEF);
    CHECK_EQ(d.payload_len, 20);
    CHECK_MEM(d.payload, payload, 20);
}

TEST(frame_encode_rejects_bad_sizes)
{
    uint8_t big[OP_FRAME_MAX];
    uint8_t out[OP_FRAME_MAX + 8];
    op_frame_t f = {OP_PROTO_VERSION, 1, 0, 1, big, OP_FRAME_MAX - OP_FRAME_HEADER - OP_FRAME_CRC};
    memset(big, 0, sizeof big);
    CHECK_EQ(op_frame_encode(&f, out, sizeof out), OP_FRAME_MAX); /* exactly max fits */
    f.payload_len++;
    CHECK_EQ(op_frame_encode(&f, out, sizeof out), -OP_ERR_TOO_LARGE);
    f.payload_len = 10;
    CHECK_EQ(op_frame_encode(&f, out, 10), -OP_ERR_TOO_LARGE); /* output buffer too small */
    CHECK_EQ(op_frame_encode(NULL, out, sizeof out), -OP_ERR_BAD_ARG);
    f.payload = NULL; /* non-zero length without data */
    CHECK_EQ(op_frame_encode(&f, out, sizeof out), -OP_ERR_BAD_ARG);
}

TEST(frame_decode_detects_corruption)
{
    uint8_t buf[32];
    op_frame_t f = {OP_PROTO_VERSION, OP_CMD_GET_STATUS, 0, 1, NULL, 0};
    int n = op_frame_encode(&f, buf, sizeof buf);
    op_frame_t d;
    for (int i = 0; i < n; i++) { /* every single bit flip must be rejected */
        for (int bit = 0; bit < 8; bit++) {
            uint8_t copy[32];
            memcpy(copy, buf, (size_t)n);
            copy[i] ^= (uint8_t)(1u << bit);
            CHECK(op_frame_decode(copy, (size_t)n, &d) != 0);
        }
    }
    CHECK_EQ(op_frame_decode(buf, (size_t)n - 1, &d), -OP_ERR_FRAME);   /* truncated */
    CHECK_EQ(op_frame_decode(buf, 5, &d), -OP_ERR_FRAME);
    CHECK_EQ(op_frame_decode(NULL, 9, &d), -OP_ERR_BAD_ARG);
    uint8_t longer[40];
    memcpy(longer, buf, (size_t)n);
    longer[n] = 0;
    CHECK_EQ(op_frame_decode(longer, (size_t)n + 1, &d), -OP_ERR_FRAME); /* trailing byte */
}

TEST(frame_decode_rejects_other_versions_with_valid_crc)
{
    op_frame_t f = {2, OP_CMD_GET_STATUS, 0, 1, NULL, 0};
    uint8_t buf[16];
    int n = op_frame_encode(&f, buf, sizeof buf);
    op_frame_t d;
    CHECK_EQ(op_frame_decode(buf, (size_t)n, &d), -OP_ERR_VERSION);
}

TEST(frame_decode_rejects_oversize)
{
    uint8_t buf[OP_FRAME_MAX + 16] = {0};
    op_frame_t d;
    CHECK_EQ(op_frame_decode(buf, OP_FRAME_MAX + 1, &d), -OP_ERR_FRAME);
}

/* ---- TLV ------------------------------------------------------------------ */
TEST(tlv_write_read_roundtrip_and_unknown_tags_skipped)
{
    uint8_t buf[64];
    op_tlv_w_t w;
    op_tlv_w_init(&w, buf, sizeof buf);
    op_tlv_put_u8(&w, 0x01, 0xAA);
    op_tlv_put_u16(&w, 0x70, 0xBBCC); /* unknown tag */
    op_tlv_put_u32(&w, 0x02, 0x11223344);
    CHECK(!w.overflow);
    CHECK_EQ(w.len, 3 + 4 + 6);
    static const uint8_t expect[] = {0x01, 0x01, 0xAA, 0x70, 0x02, 0xCC, 0xBB, 0x02, 0x04, 0x44, 0x33, 0x22, 0x11};
    CHECK_MEM(buf, expect, sizeof expect);
    op_tlv_r_t r;
    op_tlv_r_init(&r, buf, w.len);
    uint8_t tag, vlen;
    const uint8_t *v;
    int n = 0;
    while (op_tlv_next(&r, &tag, &v, &vlen)) n++;
    CHECK_EQ(n, 3);
    CHECK(!r.error);
}

TEST(tlv_writer_flags_overflow_and_stays_in_bounds)
{
    uint8_t buf[5];
    op_tlv_w_t w;
    op_tlv_w_init(&w, buf, sizeof buf);
    op_tlv_put_u32(&w, 1, 7); /* needs 6 */
    CHECK(w.overflow);
    CHECK_EQ(w.len, 0);
    op_tlv_put_u8(&w, 1, 7); /* later small writes must not resurrect partial state */
    CHECK(w.overflow);
}

TEST(tlv_reader_detects_truncation)
{
    static const uint8_t bad[] = {0x01, 0x04, 0xAA}; /* claims 4 bytes, has 1 */
    op_tlv_r_t r;
    op_tlv_r_init(&r, bad, sizeof bad);
    uint8_t tag, vlen;
    const uint8_t *v;
    CHECK(!op_tlv_next(&r, &tag, &v, &vlen));
    CHECK(r.error);
    static const uint8_t lone[] = {0x01};
    op_tlv_r_init(&r, lone, 1);
    CHECK(!op_tlv_next(&r, &tag, &v, &vlen));
    CHECK(r.error);
}

/* ---- commands -------------------------------------------------------------- */
static void cmd_roundtrip(const op_cmd_t *in, op_cmd_t *out)
{
    uint8_t buf[200];
    int n = op_cmd_encode_payload(in, buf, sizeof buf);
    CHECK(n >= 0);
    CHECK_EQ(op_cmd_decode(in->type, in->seq, buf, (size_t)n, out), 0);
    CHECK_EQ(out->type, in->type);
    CHECK_EQ(out->seq, in->seq);
}

TEST(cmd_roundtrip_simple_commands)
{
    static const uint8_t types[] = {OP_CMD_GET_STATUS, OP_CMD_CANCEL_TEMP_BASAL, OP_CMD_CANCEL_BOLUS,
                                    OP_CMD_SUSPEND, OP_CMD_RESUME};
    for (size_t i = 0; i < sizeof types; i++) {
        op_cmd_t c = {0}, d;
        c.type = types[i];
        c.seq = 9;
        cmd_roundtrip(&c, &d);
        CHECK(!d.has_time_of_day);
    }
}

TEST(cmd_roundtrip_basal_schedule_24_segments)
{
    op_cmd_t c = {0}, d;
    c.type = OP_CMD_SET_BASAL_SCHEDULE;
    c.u.basal.count = 24;
    for (uint8_t i = 0; i < 24; i++) c.u.basal.seg[i] = (op_basal_seg_t){(uint8_t)(i * 2), 50u * (i + 1)};
    cmd_roundtrip(&c, &d);
    CHECK_EQ(d.u.basal.count, 24);
    CHECK_EQ(d.u.basal.seg[23].start_slot, 46);
    CHECK_EQ(d.u.basal.seg[23].rate_mu_h, 1200);
}

TEST(cmd_roundtrip_temp_bolus_fill_ack_history)
{
    op_cmd_t c = {0}, d;
    c.type = OP_CMD_SET_TEMP_BASAL;
    c.u.temp.rate_mu_h = 2350;
    c.u.temp.duration_min = 90;
    cmd_roundtrip(&c, &d);
    CHECK_EQ(d.u.temp.rate_mu_h, 2350);
    CHECK_EQ(d.u.temp.duration_min, 90);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_BOLUS;
    c.u.bolus.amount_mu = 24950;
    cmd_roundtrip(&c, &d);
    CHECK_EQ(d.u.bolus.amount_mu, 24950);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_FILL_PRIME;
    c.u.fill.sub_op = OP_SUBOP_FILL;
    c.u.fill.fill_mu = 180000;
    cmd_roundtrip(&c, &d);
    CHECK_EQ(d.u.fill.sub_op, OP_SUBOP_FILL);
    CHECK_EQ(d.u.fill.fill_mu, 180000);
    memset(&c, 0, sizeof c);
    c.type = OP_CMD_FILL_PRIME;
    c.u.fill.sub_op = OP_SUBOP_PRIME;
    c.u.fill.prime_steps = 30;
    cmd_roundtrip(&c, &d);
    CHECK_EQ(d.u.fill.prime_steps, 30);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_ACKNOWLEDGE;
    c.u.ack.fault_mask = 0x0005;
    cmd_roundtrip(&c, &d);
    CHECK_EQ(d.u.ack.fault_mask, 5);

    memset(&c, 0, sizeof c);
    c.type = OP_CMD_GET_HISTORY;
    c.u.history.from_id = 0xDEADBEEF;
    c.u.history.max_events = 4;
    cmd_roundtrip(&c, &d);
    CHECK_EQ(d.u.history.from_id, 0xDEADBEEF);
    CHECK_EQ(d.u.history.max_events, 4);
}

TEST(cmd_time_of_day_is_optional_on_any_command)
{
    op_cmd_t c = {0}, d;
    c.type = OP_CMD_GET_STATUS;
    c.has_time_of_day = true;
    c.time_of_day_ms = 12 * 3600000u;
    cmd_roundtrip(&c, &d);
    CHECK(d.has_time_of_day);
    CHECK_EQ(d.time_of_day_ms, 12 * 3600000u);
}

TEST(cmd_ack_defaults_to_all_and_history_defaults)
{
    op_cmd_t d;
    CHECK_EQ(op_cmd_decode(OP_CMD_ACKNOWLEDGE, 1, NULL, 0, &d), 0);
    CHECK_EQ(d.u.ack.fault_mask, 0xFFFF);
    CHECK_EQ(op_cmd_decode(OP_CMD_GET_HISTORY, 1, NULL, 0, &d), 0);
    CHECK_EQ(d.u.history.from_id, 0);
    CHECK_EQ(d.u.history.max_events, OP_HIST_MAX_PER_RESPONSE);
}

TEST(cmd_decode_rejects_malformed_input)
{
    op_cmd_t d;
    static const uint8_t short_amount[] = {OP_TAG_AMOUNT_MU, 2, 1, 2};
    CHECK_EQ(op_cmd_decode(OP_CMD_BOLUS, 1, short_amount, sizeof short_amount, &d), -OP_ERR_FRAME);
    CHECK_EQ(op_cmd_decode(OP_CMD_BOLUS, 1, NULL, 0, &d), -OP_ERR_FRAME);          /* amount required */
    CHECK_EQ(op_cmd_decode(OP_CMD_SET_TEMP_BASAL, 1, NULL, 0, &d), -OP_ERR_FRAME);
    CHECK_EQ(op_cmd_decode(OP_CMD_SET_BASAL_SCHEDULE, 1, NULL, 0, &d), -OP_ERR_FRAME); /* needs >= 1 seg */
    CHECK_EQ(op_cmd_decode(OP_CMD_FILL_PRIME, 1, NULL, 0, &d), -OP_ERR_FRAME);
    CHECK_EQ(op_cmd_decode(0x7E, 1, NULL, 0, &d), -OP_ERR_UNSUPPORTED);
    static const uint8_t trunc[] = {OP_TAG_AMOUNT_MU, 4, 1};
    CHECK_EQ(op_cmd_decode(OP_CMD_BOLUS, 1, trunc, sizeof trunc, &d), -OP_ERR_FRAME);
    CHECK_EQ(op_cmd_decode(OP_CMD_BOLUS, 1, NULL, 0, NULL), -OP_ERR_BAD_ARG);

    uint8_t many[2 + 25 * 5];
    op_tlv_w_t w;
    op_tlv_w_init(&w, many, sizeof many);
    for (int i = 0; i < 25; i++) {
        uint8_t seg[3] = {(uint8_t)i, 0, 0};
        op_tlv_put(&w, OP_TAG_BASAL_SEG, seg, 3);
    }
    CHECK_EQ(op_cmd_decode(OP_CMD_SET_BASAL_SCHEDULE, 1, many, w.len, &d), -OP_ERR_FRAME); /* 25 > 24 */
}

TEST(cmd_decode_ignores_unknown_tags)
{
    static const uint8_t p[] = {0x77, 1, 9, OP_TAG_AMOUNT_MU, 4, 0x64, 0, 0, 0};
    op_cmd_t d;
    CHECK_EQ(op_cmd_decode(OP_CMD_BOLUS, 1, p, sizeof p, &d), 0);
    CHECK_EQ(d.u.bolus.amount_mu, 100);
}

TEST(cmd_encode_reports_overflow_and_unknown)
{
    op_cmd_t c = {0};
    uint8_t tiny[3];
    c.type = OP_CMD_BOLUS;
    CHECK_EQ(op_cmd_encode_payload(&c, tiny, sizeof tiny), -OP_ERR_TOO_LARGE);
    c.type = 0x55;
    CHECK_EQ(op_cmd_encode_payload(&c, tiny, sizeof tiny), -OP_ERR_UNSUPPORTED);
}

/* ---- responses ------------------------------------------------------------- */
TEST(rsp_roundtrip_status)
{
    op_rsp_t r = {0}, d;
    r.type = OP_CMD_GET_STATUS;
    r.seq = 77;
    r.result = OP_OK;
    r.has_status = true;
    r.status = (op_status_t){OP_ST_SUSPENDED | OP_ST_ALARM, 0x0003, 3812, 2100, 25, 1000, OP_FW_VERSION,
                             123456, 750, 99999, 100000, 4242, 0xBEEF, 1, 20, 500, 26100, 0xCAFE0001u, 3600, OP_ROLE_B, OP_DS_PAUSED_UNDOCKED};
    uint8_t buf[200];
    int n = op_rsp_encode_payload(&r, buf, sizeof buf);
    CHECK(n > 0);
    CHECK_EQ(op_rsp_decode(r.type, r.seq, buf, (size_t)n, &d), 0);
    CHECK(d.has_status);
    CHECK_EQ(d.status.flags, OP_ST_SUSPENDED | OP_ST_ALARM);
    CHECK_EQ(d.status.faults, 3);
    CHECK_EQ(d.status.battery_mv, 3812);
    CHECK_EQ(d.status.temp_rate_mu_h, 2100);
    CHECK_EQ(d.status.temp_remaining_min, 25);
    CHECK_EQ(d.status.current_rate_mu_h, 1000);
    CHECK_EQ(d.status.fw_version, OP_FW_VERSION);
    CHECK_EQ(d.status.reservoir_mu, 123456);
    CHECK_EQ(d.status.bolus_remaining_mu, 750);
    CHECK_EQ(d.status.delivered_mu, 99999);
    CHECK_EQ(d.status.scheduled_mu, 100000);
    CHECK_EQ(d.status.next_event_id, 4242);
    CHECK_EQ(d.status.last_seq, 0xBEEF);
    CHECK_EQ(d.status.cal_drive_id, 1);
    CHECK_EQ(d.status.cal_steps_per_rev, 20);
    CHECK_EQ(d.status.cal_gear_ratio_x100, 500);
    CHECK_EQ(d.status.cal_uu_per_step, 26100);
    CHECK_EQ(d.status.pair_id, 0xCAFE0001u);
    CHECK_EQ(d.status.wear_s, 3600);
    CHECK_EQ(d.status.role, OP_ROLE_B);
    CHECK_EQ(d.status.delivery_state, OP_DS_PAUSED_UNDOCKED);
    CHECK_EQ(d.result, OP_OK);
}

TEST(rsp_roundtrip_history)
{
    op_rsp_t r = {0}, d;
    r.type = OP_CMD_GET_HISTORY;
    r.seq = 5;
    r.has_history = true;
    r.next_event_id = 100;
    r.oldest_event_id = 20;
    r.n_events = 3;
    for (int i = 0; i < 3; i++) r.events[i] = (op_event_t){(uint32_t)(98 + i), 1000u + (uint32_t)i, OP_EV_BOLUS_START, -5 * i, 7};
    uint8_t buf[200];
    int n = op_rsp_encode_payload(&r, buf, sizeof buf);
    CHECK(n > 0);
    CHECK_EQ(op_rsp_decode(r.type, r.seq, buf, (size_t)n, &d), 0);
    CHECK(d.has_history);
    CHECK_EQ(d.n_events, 3);
    CHECK_EQ(d.next_event_id, 100);
    CHECK_EQ(d.oldest_event_id, 20);
    CHECK_EQ(d.events[2].id, 100);
    CHECK_EQ(d.events[2].a, -10);
    CHECK_EQ(d.events[2].b, 7);
    CHECK_EQ(d.events[1].time_s, 1001);
    CHECK_EQ(d.events[1].type, OP_EV_BOLUS_START);
}

TEST(rsp_result_only_and_errors)
{
    op_rsp_t r = {0}, d;
    r.type = OP_CMD_BOLUS;
    r.result = OP_ERR_LIMIT;
    uint8_t buf[16];
    int n = op_rsp_encode_payload(&r, buf, sizeof buf);
    CHECK_EQ(n, 3);
    CHECK_EQ(op_rsp_decode(r.type, 1, buf, (size_t)n, &d), 0);
    CHECK_EQ(d.result, OP_ERR_LIMIT);
    CHECK(!d.has_status);
    CHECK_EQ(op_rsp_decode(r.type, 1, NULL, 0, &d), -OP_ERR_FRAME); /* result is mandatory */
    CHECK_EQ(op_rsp_encode_payload(&r, buf, 2), -OP_ERR_TOO_LARGE);
    static const uint8_t bad[] = {OP_TAG_RESULT, 2, 0, 0};
    CHECK_EQ(op_rsp_decode(r.type, 1, bad, sizeof bad, &d), -OP_ERR_FRAME);
    /* too many history events */
    uint8_t big[400];
    op_tlv_w_t w;
    op_tlv_w_init(&w, big, sizeof big);
    op_tlv_put_u8(&w, OP_TAG_RESULT, 0);
    for (int i = 0; i < 11; i++) {
        uint8_t ev[17] = {0};
        op_tlv_put(&w, OP_TAG_HISTORY_EVENT, ev, 17);
    }
    CHECK_EQ(op_rsp_decode(OP_CMD_GET_HISTORY, 1, big, w.len, &d), -OP_ERR_FRAME);
    static const uint8_t shortev[] = {OP_TAG_RESULT, 1, 0, OP_TAG_HISTORY_EVENT, 2, 1, 2};
    CHECK_EQ(op_rsp_decode(OP_CMD_GET_HISTORY, 1, shortev, sizeof shortev, &d), -OP_ERR_FRAME);
}

TEST(rsp_full_history_response_fits_one_frame)
{
    op_rsp_t r = {0};
    r.type = OP_CMD_GET_HISTORY;
    r.has_history = true;
    r.n_events = OP_HIST_MAX_PER_RESPONSE;
    uint8_t buf[OP_FRAME_MAX];
    int n = op_rsp_encode_payload(&r, buf, sizeof buf);
    CHECK(n > 0);
    CHECK((size_t)n + OP_FRAME_HEADER + OP_FRAME_CRC + OP_CCM_TAG_LEN <= OP_FRAME_MAX);
}

TEST(frame_golden_bolus_ok_response)
{
    static const uint8_t golden[] = {0x01, 0x85, 0x02, 0x02, 0x01, 0x03, 0x00, 0x01, 0x01, 0x00, 0x34, 0x06};
    op_rsp_t r = {0};
    r.type = OP_CMD_BOLUS;
    r.seq = 0x0102;
    uint8_t body[16], out[32];
    int bl = op_rsp_encode_payload(&r, body, sizeof body);
    CHECK_EQ(bl, 3);
    op_frame_t f = {OP_PROTO_VERSION, OP_CMD_BOLUS | OP_RSP_BIT, OP_FLAG_RESPONSE, r.seq, body, (uint16_t)bl};
    int n = op_frame_encode(&f, out, sizeof out);
    CHECK_EQ(n, sizeof golden);
    CHECK_MEM(out, golden, sizeof golden);
}
