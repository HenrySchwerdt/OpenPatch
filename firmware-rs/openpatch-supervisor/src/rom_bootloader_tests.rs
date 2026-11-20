//! Unit tests of the ROM bootloader framing (in the crate because the flash-modifying encoders are crate private).
use crate::rom_bootloader::*;

#[test]
fn command_frames_are_the_code_and_its_complement() {
    let want = [
        (Command::Get, [0x00, 0xFF]),
        (Command::GetVersion, [0x01, 0xFE]),
        (Command::GetId, [0x02, 0xFD]),
        (Command::ReadMemory, [0x11, 0xEE]),
        (Command::Go, [0x21, 0xDE]),
        (Command::WriteMemory, [0x31, 0xCE]),
        (Command::Erase, [0x43, 0xBC]),
        (Command::ExtendedErase, [0x44, 0xBB]),
        (Command::WriteProtect, [0x63, 0x9C]),
        (Command::WriteUnprotect, [0x73, 0x8C]),
        (Command::ReadoutProtect, [0x82, 0x7D]),
        (Command::ReadoutUnprotect, [0x92, 0x6D]),
    ];
    for (c, f) in want {
        assert_eq!(command_frame(c), f, "{c:?}");
        assert_eq!(Command::from_code(c.code()), Some(c));
    }
    assert_eq!(Command::from_code(0x55), None);
}

#[test]
fn only_the_read_only_commands_have_a_public_frame() {
    for c in [Command::Get, Command::GetVersion, Command::GetId, Command::ReadMemory] {
        assert!(!c.modifies_flash());
        assert_eq!(read_only_command_frame(c), Some(command_frame(c)));
    }
    for c in [
        Command::Go,
        Command::WriteMemory,
        Command::Erase,
        Command::ExtendedErase,
        Command::WriteProtect,
        Command::WriteUnprotect,
        Command::ReadoutProtect,
        Command::ReadoutUnprotect,
    ] {
        assert!(c.modifies_flash(), "{c:?}");
        assert_eq!(read_only_command_frame(c), None, "{c:?}");
    }
}

#[test]
fn address_frame_is_msb_first_with_xor() {
    assert_eq!(address_frame(0x0800_0000), [0x08, 0x00, 0x00, 0x00, 0x08]);
    assert_eq!(address_frame(0x0800_1234), [0x08, 0x00, 0x12, 0x34, 0x2E]);
    assert_eq!(address_frame(0xFFFF_FFFF), [0xFF, 0xFF, 0xFF, 0xFF, 0x00]);
}

#[test]
fn read_length_frame_bounds() {
    assert_eq!(read_length_frame(1), Ok([0x00, 0xFF]));
    assert_eq!(read_length_frame(256), Ok([0xFF, 0x00]));
    assert_eq!(read_length_frame(16), Ok([0x0F, 0xF0]));
    assert_eq!(read_length_frame(0), Err(FrameError::Length));
    assert_eq!(read_length_frame(257), Err(FrameError::Length));
}

#[test]
fn write_data_frame_layout_checksum_and_limits() {
    let data = [0x11u8, 0x22, 0x33, 0x44, 0x55, 0x66, 0x77, 0x88];
    let mut out = [0u8; MAX_FRAME];
    let n = write_data_frame(&data, &mut out).unwrap();
    assert_eq!(n, 10);
    assert_eq!(out[0], 7, "N - 1");
    assert_eq!(&out[1..9], &data);
    assert_eq!(out[9], 7 ^ xor(&data));
    let big = [0xA5u8; 256];
    let n = write_data_frame(&big, &mut out).unwrap();
    assert_eq!(n, 258);
    assert_eq!(out[0], 255);
    assert_eq!(out[257], 255 ^ xor(&big));
    assert_eq!(write_data_frame(&[], &mut out), Err(FrameError::Length));
    assert_eq!(write_data_frame(&[0u8; 257], &mut out), Err(FrameError::Length));
    assert_eq!(write_data_frame(&[0u8; 12], &mut out), Err(FrameError::Alignment));
    assert_eq!(write_data_frame(&data, &mut out[..9]), Err(FrameError::Buffer));
}

#[test]
fn write_address_rules() {
    assert_eq!(check_write_address(0x0800_0000), Ok(()));
    assert_eq!(check_write_address(0x0800_0008), Ok(()));
    assert_eq!(check_write_address(0x0800_0004), Err(FrameError::Address));
    assert_eq!(check_write_address(0x0000_0000), Err(FrameError::Address), "never below the flash window");
}

#[test]
fn extended_erase_payloads() {
    assert_eq!(extended_erase_special(SpecialErase::Mass), [0xFF, 0xFF, 0x00]);
    assert_eq!(extended_erase_special(SpecialErase::Bank1), [0xFF, 0xFE, 0x01]);
    assert_eq!(extended_erase_special(SpecialErase::Bank2), [0xFF, 0xFD, 0x02]);
    let mut out = [0u8; MAX_FRAME];
    let n = extended_erase_pages(&[0, 1, 2], &mut out).unwrap();
    assert_eq!(&out[..n], &[0x00, 0x02, 0, 0, 0, 1, 0, 2, 0x01]);
    let n = extended_erase_pages(&[0x0105], &mut out).unwrap();
    assert_eq!(&out[..n], &[0x00, 0x00, 0x01, 0x05, 0x04]);
    assert_eq!(extended_erase_pages(&[], &mut out), Err(FrameError::Pages));
    assert_eq!(extended_erase_pages(&[0; MAX_ERASE_PAGES + 1], &mut out), Err(FrameError::Pages));
    assert!(extended_erase_pages(&[0; MAX_ERASE_PAGES], &mut out).is_ok());
    assert_eq!(extended_erase_pages(&[1, 2, 3], &mut out[..5]), Err(FrameError::Buffer));
}

#[test]
fn replies_and_page_numbers() {
    assert_eq!(parse_reply(0x79), Reply::Ack);
    assert_eq!(parse_reply(0x1F), Reply::Nack);
    assert_eq!(parse_reply(0x00), Reply::Unknown(0));
    assert_eq!(page_of(0x0800_0000, 2048), Some(0));
    assert_eq!(page_of(0x0800_0800, 2048), Some(1));
    assert_eq!(page_of(0x0800_3FFF, 2048), Some(7));
    assert_eq!(page_of(0x0700_0000, 2048), None);
    assert_eq!(page_of(0x0800_0000, 0), None);
}

#[test]
fn get_reply_parsing() {
    let cmds = [0x00u8, 0x01, 0x02, 0x11, 0x21, 0x31, 0x44, 0x63, 0x73, 0x82, 0x92];
    let mut r = [0u8; 15];
    r[0] = ACK;
    r[1] = 11;
    r[2] = 0x31;
    r[3..14].copy_from_slice(&cmds);
    r[14] = ACK;
    let g = parse_get(&r).unwrap();
    assert_eq!((g.version, g.n_commands), (0x31, 11));
    assert!(g.supports(Command::ExtendedErase) && g.supports(Command::WriteMemory));
    assert!(!g.supports(Command::Erase), "the legacy erase is absent: use the extended one");
    assert_eq!(parse_get(&r[..14]), Err(ParseError::Length));
    let mut bad = r;
    bad[14] = NACK;
    assert_eq!(parse_get(&bad), Err(ParseError::NoAck));
    let mut bad = r;
    bad[0] = NACK;
    assert_eq!(parse_get(&bad), Err(ParseError::NoAck));
    assert_eq!(parse_get(&[ACK, 1]), Err(ParseError::Length));
}

#[test]
fn get_id_parsing() {
    assert_eq!(parse_get_id(&[ACK, 1, 0x04, 0x43, ACK]), Ok(PID_STM32C011));
    assert_eq!(parse_get_id(&[ACK, 1, 0x04, 0x43]), Err(ParseError::Length));
    assert_eq!(parse_get_id(&[NACK, 1, 0x04, 0x43, ACK]), Err(ParseError::NoAck));
    assert_eq!(parse_get_id(&[ACK, 2, 0x04, 0x43, ACK]), Err(ParseError::Length));
}

#[test]
fn blocks_split_an_image_and_pad_the_tail() {
    let img: [u8; 40] = core::array::from_fn(|i| i as u8);
    let mut it = Blocks::new(0x0800_0000, &img, 16).unwrap();
    let got: [(u32, usize); 3] = [it.next().map(|x| (x.0, x.1.len())).unwrap(), it.next().map(|x| (x.0, x.1.len())).unwrap(), it.next().map(|x| (x.0, x.1.len())).unwrap()];
    assert!(it.next().is_none());
    assert_eq!(got, [(0x0800_0000, 16), (0x0800_0010, 16), (0x0800_0020, 8)]);
    assert!(Blocks::new(0x0800_0004, &img, 16).is_err(), "unaligned start");
    assert!(Blocks::new(0x0800_0000, &img[..12], 16).is_err(), "unpadded tail");
    assert!(Blocks::new(0x0800_0000, &img, 12).is_err(), "block size not a multiple of 8");
    assert!(Blocks::new(0x0800_0000, &img, 264).is_err(), "block above 256");
    assert_eq!(padded_len(1), 8);
    assert_eq!(padded_len(8), 8);
    assert_eq!(padded_len(9), 16);
    let mut dst = [0u8; 16];
    assert_eq!(pad_tail(&[1, 2, 3], &mut dst[..8]), Ok(8));
    assert_eq!(&dst[..8], &[1, 2, 3, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF]);
    assert_eq!(pad_tail(&[0; 9], &mut dst[..8]), Err(FrameError::Buffer));
}

#[test]
fn strap_sequences() {
    assert_eq!(ENTRY[0], StrapStep::Boot0(true), "BOOT0 is set before the reset pulse");
    assert_eq!(ENTRY[1], StrapStep::NrstLow(true));
    assert_eq!(ENTRY[2], StrapStep::WaitMs(10));
    assert_eq!(ENTRY[4], StrapStep::WaitMs(100));
    assert_eq!(ENTRY[5], StrapStep::UartEven);
    assert_eq!(ENTRY[6], StrapStep::SendInit);
    assert_eq!(EXIT[0], StrapStep::Boot0(false), "BOOT0 is released before the reset pulse");
    assert!(EXIT.contains(&StrapStep::UartNone));
}
