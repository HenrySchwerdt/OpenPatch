//! TMAG5273 register map and decoding against datasheet SLYS045C values.
use openpatch_core::tmag5273::*;

#[test]
fn i2c_address_variants_table_6_2() {
    assert_eq!([ADDR_A, ADDR_B, ADDR_C, ADDR_D], [0x35, 0x22, 0x78, 0x44]);
}

#[test]
fn register_offsets_table_8_1() {
    assert_eq!(REG_DEVICE_CONFIG_1, 0x00);
    assert_eq!(REG_DEVICE_CONFIG_2, 0x01);
    assert_eq!(REG_SENSOR_CONFIG_1, 0x02);
    assert_eq!(REG_SENSOR_CONFIG_2, 0x03);
    assert_eq!(REG_DEVICE_ID, 0x0D);
    assert_eq!(REG_MANUFACTURER_ID_LSB, 0x0E);
    assert_eq!(REG_CONV_STATUS, 0x18);
    assert_eq!(REG_ANGLE_RESULT_MSB, 0x19);
    assert_eq!(REG_ANGLE_RESULT_LSB, 0x1A);
    assert_eq!(REG_MAGNITUDE_RESULT, 0x1B);
    assert_eq!(REG_DEVICE_STATUS, 0x1C);
    assert_eq!(MANUFACTURER_ID, [0x49, 0x54]);
}

#[test]
fn angle_examples_from_section_6_5_2_3() {
    // 354.50 deg = 0001 0110 0010 1000b ; 17.25 deg = 0000 0001 0001 0100b
    assert_eq!(angle_raw(0x16, 0x28), Some(5672)); // 354.5 * 16
    assert_eq!(angle_raw(0x01, 0x14), Some(276)); // 17.25 * 16
}

#[test]
fn angle_counts_cardinal_points() {
    assert_eq!(angle_counts(0x00, 0x00), Some(0));
    // 90 deg = 1440 = 0x05A0 -> 1024 counts
    assert_eq!(angle_counts(0x05, 0xA0), Some(1024));
    // 180 deg = 2880 = 0x0B40 -> 2048
    assert_eq!(angle_counts(0x0B, 0x40), Some(2048));
    // 270 deg = 4320 = 0x10E0 -> 3072
    assert_eq!(angle_counts(0x10, 0xE0), Some(3072));
    // last valid code 359.9375 deg = 5759 = 0x167F -> 4095 (never 4096)
    assert_eq!(angle_counts(0x16, 0x7F), Some(4095));
}

#[test]
fn angle_rejects_reserved_bits_and_out_of_range() {
    assert_eq!(angle_raw(0x20, 0x00), None); // D13 set
    assert_eq!(angle_raw(0x80, 0x00), None); // D15 set
    assert_eq!(angle_raw(0x16, 0x80), None); // 5760 = 360.0 deg
    assert_eq!(angle_raw(0x1F, 0xFF), None);
}

#[test]
fn angle_is_monotonic_and_step_is_small() {
    let mut last = 0u16;
    for raw in 0..5760u16 {
        let c = angle_counts((raw >> 8) as u8, raw as u8).unwrap();
        assert!(c >= last && c - last <= 1, "raw {raw}");
        last = c;
    }
}

#[test]
fn crc_examples_from_section_6_5_1_3_6() {
    assert_eq!(crc8(&[0x00]), 0xF3);
    assert_eq!(crc8(&[0xFF]), 0x00);
    assert_eq!(crc8(&[0x80]), 0x7A);
    assert_eq!(crc8(&[0x4C]), 0x10);
    assert_eq!(crc8(&[0xE0]), 0x5D);
    assert_eq!(crc8(&[0, 0, 0, 0]), 0xD1);
    assert_eq!(crc8(&[0xFF; 4]), 0x0F);
}

#[test]
fn config_matches_register_fields() {
    let w = config_writes(false);
    assert_eq!(w[0], (0x00, 0x00));
    // MAG_CH_EN (7:4) = 3 (X, Y)
    assert_eq!(w[1], (0x02, 3 << 4));
    // ANGLE_EN (3:2) = 1 (X first, Y second); X_Y_RANGE = 0
    assert_eq!(w[2], (0x03, 1 << 2));
    // OPERATING_MODE (1:0) = 2 continuous, written last
    assert_eq!(w[3], (0x01, 0x02));
    assert_eq!(config_writes(true)[0], (0x00, 0x80));
}

fn frame(status: u8, msb: u8, lsb: u8, mag: u8) -> [u8; FRAME_LEN] {
    [status, msb, lsb, mag]
}

#[test]
fn decode_frame_ok_and_with_crc() {
    let f = frame(0x41, 0x05, 0xA0, 77);
    let s = decode_frame(&f, None).unwrap();
    assert_eq!((s.counts, s.magnitude, s.set_count), (1024, 77, 2));
    assert_eq!(decode_frame(&f, Some(crc8(&f))).unwrap(), s);
    assert_eq!(decode_frame(&f, Some(crc8(&f) ^ 1)), Err(FrameError::Crc));
}

#[test]
fn decode_frame_rejects_por_diag_and_bad_angle() {
    assert_eq!(decode_frame(&frame(0x10, 0, 0, 1), None), Err(FrameError::PowerOnReset));
    assert_eq!(decode_frame(&frame(0x02, 0, 0, 1), None), Err(FrameError::Diag));
    assert_eq!(decode_frame(&frame(0x01, 0x20, 0, 1), None), Err(FrameError::BadAngle));
}

#[test]
fn torn_read_detection_uses_set_count_only() {
    assert!(!torn(0x41, 0x41));
    assert!(!torn(0x41, 0x40)); // RESULT_STATUS bit differs: not a new data set
    assert!(torn(0x41, 0x61));
}
