import Foundation

/// OpenPatch protocol v1 wire format, as specified in firmware/docs/openpatch-protocol.md (draft v1).
///
///     version u8 | type u8 | flags u8 | seq u16 LE | len u16 LE | payload (TLV list) | crc16 LE
///
/// All integers little-endian, amounts in mU (0.001 U), rates in mU/h. One frame per GATT write / notification.
public enum V1 {
    public static let version: UInt8 = 0x01
    public static let headerSize = 7
    public static let crcSize = 2
    /// ATT MTU 247 - 3. The phone must negotiate an MTU >= 247 before the first command.
    public static let maxFrameSize = 244
    public static let responseFlag: UInt8 = 0x80
    /// Events per `GetHistory` response (`HIST_MAX_PER_RESPONSE`).
    public static let historyPageSize = 10
    public static let flagEncrypted: UInt8 = 0x01
    public static let flagResponse: UInt8 = 0x02

    public enum CommandID: UInt8, CaseIterable {
        case getStatus = 0x01, setBasalSchedule, setTempBasal, cancelTempBasal, bolus, cancelBolus
        case suspend, resume, fillPrime, acknowledge, getHistory
        case setPairing = 0x0C, activate = 0x0D, release = 0x0E
        /// Extension (Rust pod): refill with a fixed-rate plunger retraction (`FILL_MU` mU, 0 cancels). On the cup pod this is
        /// the assisted PRESSURE fill (the user pushes the syringe); other drives may also use it as a suction draw.
        case assistedFill = 0x0F
        /// Diagnostics (docs/06-diagnostics.md 5.4). Ids 0x20..0x22 so that the response types 0xA0..0xA2 never collide with
        /// the Alert notification frame type 0x90 (the first draft used 0x10..0x12 and `GetFaultLog` answered as 0x90).
        case getFaultLog = 0x20, runSelfTest = 0x21, clearDiag = 0x22
    }

    /// Handshake frame types (requests; responses are `type | 0x80`).
    public static let handshakeTypes: [UInt8] = [0x40, 0x41, 0x42, 0x43]
    /// Frame type of unsolicited Alert notifications.
    public static let notificationType: UInt8 = 0x90

    public enum Tag: UInt8, CaseIterable {
        case result = 0x01, basalSeg, rateMUh, durationMin, amountMU, fillMU, primeSteps, subOp, faultMask
        case fromID, maxEvents, timeOfDayMS, historyEvent, nextEventID, oldestEventID
        case stateFlags = 0x10, reservoirMU, batteryMV, bolusRemainingMU, tempRateMUh, tempRemainingMin
        case currentRateMUh, deliveredMU, scheduledMU, fwVersion
        case lastSeq = 0x1A, driveCal = 0x1B, podInfo = 0x1C, pairID = 0x1D, role = 0x1E, activationID = 0x1F, actDeliveredMU = 0x20
        /// Fill / draw job of the pod (Rust extension): state (`FillState`), requested and drawn volume in mU.
        case drawState = 0x21, drawRequestedMU = 0x22, drawDoneMU = 0x23
        case notifyKind = 0x25, notifyArg = 0x26
        /// Diagnostics (docs/06-diagnostics.md 5.4).
        case diagSummary = 0x27, fruHealth = 0x28, diagRecord = 0x29, nextDiagID = 0x2A, oldestDiagID = 0x2B, diagLatched = 0x2C
        case selftestState = 0x2D, diagCode = 0x2E, podUID = 0x2F
    }

    public enum Result: UInt8, Equatable, CaseIterable {
        case ok = 0, badArg, limit, busy, fault, suspended, notSuspended, reservoir, persists, unsupported
        case frame, crc, version, replay, auth, tooLarge, hourly, notFound, session
        case notDocked, released, alreadyActive, pair, wearExpired, charging
        /// Rust extension: `Resume` / `Activate` refused because a fill or draw was not followed by a prime yet.
        case primeRequired = 26
        /// Rust extension: refill refused because the pod is docked (only an undocked pod may retract its plunger).
        case docked = 27
        /// Diagnostics: not suspended / draw or test running; Resume or Activate refused by a latched code; code not clearable.
        case selfTestRefused = 28, latched = 29, notClearable = 30
        /// Rust extension: `Resume` refused because the pod holds no basal schedule (send `SetBasalSchedule` first).
        case noSchedule = 31
    }

    public struct StateFlags: OptionSet {
        public let rawValue: UInt16
        public init(rawValue: UInt16) { self.rawValue = rawValue }
        public static let suspended = StateFlags(rawValue: 1 << 0)
        public static let bolusActive = StateFlags(rawValue: 1 << 1)
        public static let tempActive = StateFlags(rawValue: 1 << 2)
        public static let basalProgrammed = StateFlags(rawValue: 1 << 3)
        public static let reservoirLow = StateFlags(rawValue: 1 << 4)
        public static let alarm = StateFlags(rawValue: 1 << 5)
        public static let filled = StateFlags(rawValue: 1 << 6)
        public static let batteryLow = StateFlags(rawValue: 1 << 7)
        public static let wearWarning = StateFlags(rawValue: 1 << 8)
        public static let docked = StateFlags(rawValue: 1 << 9)
        public static let activePod = StateFlags(rawValue: 1 << 10)
        /// A fill / draw job is running (the pod is retracting its plunger).
        public static let drawing = StateFlags(rawValue: 1 << 11)
        /// A fill / draw happened and the mandatory prime has not been done yet.
        public static let primeRequired = StateFlags(rawValue: 1 << 12)
        /// Any W/F/L diagnostic record is active.
        public static let diagActive = StateFlags(rawValue: 1 << 13)
        /// The latched set is not empty: Resume and Activate are refused.
        public static let latched = StateFlags(rawValue: 1 << 14)
    }

    /// FAULT_MASK bits (spec 4.1).
    public enum FaultBit {
        public static let occlusion: UInt16 = 1 << 0
        public static let encoderDeviation: UInt16 = 1 << 1
        public static let reservoirEmpty: UInt16 = 1 << 2
        public static let batteryCritical: UInt16 = 1 << 3
        public static let limitExceeded: UInt16 = 1 << 4
        public static let internalError: UInt16 = 1 << 5
        public static let noCalibration: UInt16 = 1 << 6
        public static let wearExpired: UInt16 = 1 << 7
    }

    public enum HistoryType: UInt8, CaseIterable {
        case boot = 1, bolusStart, bolusDone, bolusCancel, tempStart, tempDone, tempCancel, tempCommFallback
        case basalSet, suspend, resume, fill, prime, fault, ack, lowReservoir, lowBattery
        case undocked = 18, docked, activate, release, wearWarning, wearExpired, paired
        /// Fill / draw: a = requested mU (start) or drawn mU (done / stall), b = steps (start) or requested mU.
        case drawStart = 25, drawDone, drawStall
        /// Prime finished: a = steps.
        case primeDone = 30
        /// A diagnostic record exists: a = code, b = ctx_a.
        case diag = 31
    }

    public struct TLV: Equatable {
        public var tag: UInt8
        public var value: [UInt8]
        public init(tag: UInt8, value: [UInt8]) { self.tag = tag; self.value = value }
        public init(_ tag: Tag, u8: UInt8) { self.init(tag: tag.rawValue, value: [u8]) }
        public init(_ tag: Tag, u16: UInt16) { var w = ByteWriter(); w.u16(u16); self.init(tag: tag.rawValue, value: w.bytes) }
        public init(_ tag: Tag, u32: UInt32) { var w = ByteWriter(); w.u32(u32); self.init(tag: tag.rawValue, value: w.bytes) }
    }

    public struct HistoryEvent: Equatable {
        public var id: UInt32, timeSeconds: UInt32, type: UInt8, a: Int32, b: Int32
        public init(id: UInt32, timeSeconds: UInt32, type: UInt8, a: Int32, b: Int32) {
            self.id = id; self.timeSeconds = timeSeconds; self.type = type; self.a = a; self.b = b
        }
        public var bytes: [UInt8] { var w = ByteWriter(); w.u32(id); w.u32(timeSeconds); w.u8(type); w.i32(a); w.i32(b); return w.bytes }
    }

    public struct Message: Equatable {
        public var type: UInt8
        public var flags: UInt8
        public var seq: UInt16
        public var tlvs: [TLV]
        public init(type: UInt8, flags: UInt8 = 0, seq: UInt16, tlvs: [TLV] = []) {
            self.type = type; self.flags = flags; self.seq = seq; self.tlvs = tlvs
        }
        public var isResponse: Bool { flags & V1.flagResponse != 0 }

        public func value(_ tag: Tag) -> [UInt8]? { tlvs.first { $0.tag == tag.rawValue }?.value }
        public func u8(_ tag: Tag) -> UInt8? { value(tag).flatMap { $0.count == 1 ? $0[0] : nil } }
        public func u16(_ tag: Tag) -> UInt16? {
            guard let v = value(tag), v.count == 2 else { return nil }
            var r = ByteReader(v)
            return try? r.u16()
        }
        public func u32(_ tag: Tag) -> UInt32? {
            guard let v = value(tag), v.count == 4 else { return nil }
            var r = ByteReader(v)
            return try? r.u32()
        }
        public var result: Result? { u8(.result).flatMap(Result.init(rawValue:)) }

        public var historyEvents: [HistoryEvent] {
            tlvs.filter { $0.tag == Tag.historyEvent.rawValue && $0.value.count == 17 }.compactMap { tlv in
                var r = ByteReader(tlv.value)
                guard let id = try? r.u32(), let t = try? r.u32(), let type = try? r.u8(), let a = try? r.i32(), let b = try? r.i32() else { return nil }
                return HistoryEvent(id: id, timeSeconds: t, type: type, a: a, b: b)
            }
        }
    }

    /// CRC-16/CCITT-FALSE (poly 0x1021, init 0xFFFF, no reflection, no final XOR). Check value "123456789" = 0x29B1.
    public static func crc16<S: Sequence>(_ bytes: S) -> UInt16 where S.Element == UInt8 {
        var crc: UInt16 = 0xFFFF
        for byte in bytes {
            crc ^= UInt16(byte) << 8
            for _ in 0..<8 { crc = (crc & 0x8000) != 0 ? (crc << 1) ^ 0x1021 : crc << 1 }
        }
        return crc
    }

    public static func encode(_ message: Message) -> Data {
        let payload = message.tlvs.flatMap { [$0.tag, UInt8($0.value.count)] + $0.value }
        precondition(headerSize + payload.count + crcSize <= maxFrameSize, "frame too large")
        var w = ByteWriter()
        w.u8(version); w.u8(message.type); w.u8(message.flags); w.u16(message.seq); w.u16(UInt16(payload.count))
        var bytes = w.bytes + payload
        let crc = crc16(bytes)
        bytes.append(UInt8(crc & 0xFF)); bytes.append(UInt8(crc >> 8))
        return Data(bytes)
    }

    /// Splits a TLV payload (`tag | length | value` ...). A truncated TLV is invalid; unknown tags are kept.
    static func parseTLVs(_ payload: [UInt8]) throws -> [TLV] {
        var tlvs: [TLV] = []
        var index = 0
        while index < payload.count {
            guard index + 2 <= payload.count else { throw CodecError.invalidPayload }
            let tag = payload[index], count = Int(payload[index + 1])
            guard index + 2 + count <= payload.count else { throw CodecError.invalidPayload }
            tlvs.append(TLV(tag: tag, value: Array(payload[(index + 2)..<(index + 2 + count)])))
            index += 2 + count
        }
        return tlvs
    }

    /// Checks in the order the firmware does: length consistency, CRC, version. Unknown tags are kept and skipped by readers.
    public static func decode(_ data: Data) throws -> Message {
        let bytes = [UInt8](data)
        guard bytes.count >= headerSize + crcSize else { throw CodecError.truncated }
        guard bytes.count <= maxFrameSize else { throw CodecError.badLength }
        let length = Int(bytes[5]) | Int(bytes[6]) << 8
        guard bytes.count == headerSize + length + crcSize else { throw CodecError.badLength }
        let stored = UInt16(bytes[bytes.count - 2]) | UInt16(bytes[bytes.count - 1]) << 8
        guard crc16(bytes[0..<(bytes.count - crcSize)]) == stored else { throw CodecError.badCRC }
        guard bytes[0] == version else { throw CodecError.badVersion(bytes[0]) }
        let flags = bytes[2]
        guard flags & flagEncrypted == 0 else { throw CodecError.encrypted }

        let tlvs = try parseTLVs(Array(bytes[headerSize..<(headerSize + length)]))
        return Message(type: bytes[1], flags: flags, seq: UInt16(bytes[3]) | UInt16(bytes[4]) << 8, tlvs: tlvs)
    }
}
