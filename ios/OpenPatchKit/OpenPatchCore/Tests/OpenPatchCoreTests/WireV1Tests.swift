import XCTest
@testable import OpenPatchCore

/// Byte-exact checks against the examples in firmware/docs/openpatch-protocol.md section 7.
final class WireV1Tests: XCTestCase {
    private func data(_ hex: String) -> Data {
        Data(hex.split(separator: " ").map { UInt8($0, radix: 16)! })
    }

    func test_crc16_checkValue() {
        XCTAssertEqual(V1.crc16(Array("123456789".utf8)), 0x29B1)
    }

    func test_specExample_getStatus_seq1() throws {
        let frame = data("01 01 00 01 00 00 00 BB 7A")
        XCTAssertEqual(V1.encode(V1.Message(type: 0x01, seq: 1)), frame)
        let decoded = try V1.decode(frame)
        XCTAssertEqual(decoded.type, 0x01)
        XCTAssertEqual(decoded.seq, 1)
        XCTAssertTrue(decoded.tlvs.isEmpty)
    }

    func test_specExample_bolus2U_seq0102() throws {
        let frame = data("01 05 00 02 01 06 00 05 04 D0 07 00 00 38 31")
        let message = V1.Message(type: 0x05, seq: 0x0102, tlvs: [V1.TLV(.amountMU, u32: 2000)])
        XCTAssertEqual(V1.encode(message), frame)
        XCTAssertEqual(try V1.decode(frame).u32(.amountMU), 2000)
    }

    func test_specExample_okResponse() throws {
        let frame = data("01 85 02 02 01 03 00 01 01 00 34 06")
        let message = V1.Message(type: 0x85, flags: V1.flagResponse, seq: 0x0102, tlvs: [V1.TLV(.result, u8: 0)])
        XCTAssertEqual(V1.encode(message), frame)
        let decoded = try V1.decode(frame)
        XCTAssertTrue(decoded.isResponse)
        XCTAssertEqual(decoded.result, .ok)
    }

    func test_decode_rejectsInvalidFrames() {
        var badCRC = V1.encode(V1.Message(type: 1, seq: 1))
        badCRC[badCRC.count - 1] ^= 0xFF
        XCTAssertThrowsError(try V1.decode(badCRC)) { XCTAssertEqual($0 as? CodecError, .badCRC) }

        XCTAssertThrowsError(try V1.decode(Data([1, 1, 0]))) { XCTAssertEqual($0 as? CodecError, .truncated) }

        var wrongLength = [UInt8](V1.encode(V1.Message(type: 1, seq: 1)))
        wrongLength[5] = 3
        XCTAssertThrowsError(try V1.decode(Data(wrongLength))) { XCTAssertEqual($0 as? CodecError, .badLength) }

        XCTAssertThrowsError(try V1.decode(Data(repeating: 0, count: 300))) { XCTAssertEqual($0 as? CodecError, .badLength) }
    }

    func test_decode_checksVersionAfterCRC() {
        var bytes = [UInt8](V1.encode(V1.Message(type: 1, seq: 1)))
        bytes[0] = 2
        let crc = V1.crc16(bytes[0..<(bytes.count - 2)])
        bytes[bytes.count - 2] = UInt8(crc & 0xFF); bytes[bytes.count - 1] = UInt8(crc >> 8)
        XCTAssertThrowsError(try V1.decode(Data(bytes))) { XCTAssertEqual($0 as? CodecError, .badVersion(2)) }
    }

    func test_decode_encryptedFrameWithoutCipherIsRejected() {
        var bytes = [UInt8](V1.encode(V1.Message(type: 1, seq: 1)))
        bytes[2] = V1.flagEncrypted
        let crc = V1.crc16(bytes[0..<(bytes.count - 2)])
        bytes[bytes.count - 2] = UInt8(crc & 0xFF); bytes[bytes.count - 1] = UInt8(crc >> 8)
        XCTAssertThrowsError(try V1.decode(Data(bytes))) { XCTAssertEqual($0 as? CodecError, .encrypted) }
    }

    func test_unknownTagsAreSkipped_truncatedTLVIsInvalid() throws {
        let message = V1.Message(type: 0x81, flags: V1.flagResponse, seq: 5,
                                 tlvs: [V1.TLV(tag: 0x7F, value: [1, 2, 3]), V1.TLV(.result, u8: 0)])
        let decoded = try V1.decode(V1.encode(message))
        XCTAssertEqual(decoded.result, .ok)
        XCTAssertEqual(decoded.tlvs.count, 2)

        // tag claims 5 bytes but only 1 follows; frame-level length and CRC are valid
        var bytes: [UInt8] = [1, 0x81, 2, 5, 0, 3, 0, 0x01, 0x05, 0x00]
        let crc = V1.crc16(bytes)
        bytes += [UInt8(crc & 0xFF), UInt8(crc >> 8)]
        XCTAssertThrowsError(try V1.decode(Data(bytes))) { XCTAssertEqual($0 as? CodecError, .invalidPayload) }
    }

    func test_historyEventParsing() throws {
        let event = V1.HistoryEvent(id: 70_000, timeSeconds: 3600, type: 4, a: -1, b: 2000)
        let message = V1.Message(type: 0x8B, flags: V1.flagResponse, seq: 9,
                                 tlvs: [V1.TLV(.result, u8: 0), V1.TLV(tag: V1.Tag.historyEvent.rawValue, value: event.bytes)])
        XCTAssertEqual(try V1.decode(V1.encode(message)).historyEvents, [event])
    }

    func test_maxFrameSizeIsEnforcedForBasalSchedule() {
        // 24 segments x 5 byte TLV + TOD (6) + header/CRC (9) stays well below 244
        let tlvs = (0..<24).map { V1.TLV(tag: V1.Tag.basalSeg.rawValue, value: [UInt8($0), 0, 0]) }
        XCTAssertLessThanOrEqual(V1.encode(V1.Message(type: 2, seq: 1, tlvs: tlvs)).count, V1.maxFrameSize)
    }
}
