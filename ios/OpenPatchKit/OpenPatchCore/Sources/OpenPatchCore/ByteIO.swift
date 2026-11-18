import Foundation

/// Little-endian byte writer/reader (OpenPatch protocol v1 is little-endian).
struct ByteWriter {
    private(set) var bytes: [UInt8] = []
    mutating func u8(_ v: UInt8) { bytes.append(v) }
    mutating func u16(_ v: UInt16) { bytes.append(UInt8(v & 0xFF)); bytes.append(UInt8(v >> 8)) }
    mutating func u32(_ v: UInt32) { u16(UInt16(v & 0xFFFF)); u16(UInt16(v >> 16)) }
    mutating func i32(_ v: Int32) { u32(UInt32(bitPattern: v)) }
}

struct ByteReader {
    private let bytes: [UInt8]
    private var index = 0
    init(_ bytes: [UInt8]) { self.bytes = bytes }

    mutating func u8() throws -> UInt8 {
        guard index < bytes.count else { throw CodecError.invalidPayload }
        defer { index += 1 }
        return bytes[index]
    }
    mutating func u16() throws -> UInt16 { UInt16(try u8()) | UInt16(try u8()) << 8 }
    mutating func u32() throws -> UInt32 { UInt32(try u16()) | UInt32(try u16()) << 16 }
    mutating func i32() throws -> Int32 { Int32(bitPattern: try u32()) }
}

public enum CodecError: Error, Equatable {
    case truncated        // shorter than header or declared length
    case badLength        // len field inconsistent with frame size / frame too large
    case badCRC
    case badVersion(UInt8)
    case encrypted        // flag set but no cipher configured
    case invalidPayload   // TLV with wrong length / malformed
}
