import Foundation

/// Application layer session key agreement, phone (initiator) side. Normative text: docs/04-protocol.md section 3 to 6.
/// Pod side and byte-exact reference: firmware-rs/openpatch-proto/src/handshake.rs. Both are checked against
/// docs/vectors/session-key-agreement.json.
///
/// Two handshakes of the same shape (INIT request / response, FINISH request / response, unencrypted frames):
///  * pairing (types 0x40/0x41), only while the pod's button window is open: creates the long-term pairing secret `PS`;
///  * session (types 0x42/0x43), once per BLE connection: fresh ephemeral X25519 mixed with `PS` gives one AES-128-CCM key
///    per direction and the nonce salt.
public enum SessionHandshake {
    public static let publicKeyLength = 32
    public static let nonceLength = 16
    public static let confirmLength = 16
    public static let pairingSecretLength = 32
    public static let psIDLength = 4

    public enum FrameType {
        public static let pairInit: UInt8 = 0x40
        public static let pairFinish: UInt8 = 0x41
        public static let sessionInit: UInt8 = 0x42
        public static let sessionFinish: UInt8 = 0x43
    }

    public enum Tag {
        public static let ephPub: UInt8 = 0x30
        public static let nonce: UInt8 = 0x31
        public static let confirm: UInt8 = 0x32
        public static let psID: UInt8 = 0x33
    }

    public enum Mode: UInt8 { case pair = 1, session = 2 }
    public enum Side { case app, pod }

    public enum Failure: Error, Equatable {
        case malformed
        /// The pod answered with this RESULT (14 = window closed / bad tag, 18 = out of order, 22 = pair again).
        case rejected(UInt8)
        /// The pod's key confirmation did not verify: wrong pairing secret, wrong OOB code, or a man in the middle.
        case badConfirmation
        case lowOrderPoint
    }

    /// Directional AES-128-CCM keys of one session. Never log them.
    public struct SessionKeys: Equatable {
        public let keyC2P: [UInt8]   // phone -> pod, nonce direction 0
        public let keyP2C: [UInt8]   // pod -> phone, nonce directions 1 and 2
        public let salt: [UInt8]     // 4 byte nonce prefix
        public init(keyC2P: [UInt8], keyP2C: [UInt8], salt: [UInt8]) { self.keyC2P = keyC2P; self.keyP2C = keyP2C; self.salt = salt }
    }

    public enum Outcome: Equatable {
        case paired(secret: [UInt8])
        case session(SessionKeys)
    }

    // MARK: Key schedule (pure functions)

    private static func ascii(_ s: String) -> [UInt8] { Array(s.utf8) }

    /// 32 zero bytes without an out-of-band code, else `SHA-256("OPENPATCH/1 oob" || oob)`.
    public static func oobSalt(_ oob: [UInt8]) -> [UInt8] {
        oob.isEmpty ? [UInt8](repeating: 0, count: 32) : SessionCrypto.sha256(ascii("OPENPATCH/1 oob") + oob)
    }

    /// `HKDF-Expand(PS, "OPENPATCH/1 ps-id", 4)`.
    public static func psID(_ ps: [UInt8]) -> [UInt8] {
        SessionCrypto.hkdfExpand(prk: ps, info: ascii("OPENPATCH/1 ps-id"), length: psIDLength)
    }

    /// `SHA-256("OPENPATCH/1 transcript" || mode || ps_id || pubA || pubB || nonceA || nonceB)`; ps_id is zero for pairing.
    public static func transcriptHash(mode: Mode, psID: [UInt8], pubA: [UInt8], pubB: [UInt8], nonceA: [UInt8], nonceB: [UInt8]) -> [UInt8] {
        let parts: [[UInt8]] = [ascii("OPENPATCH/1 transcript"), [mode.rawValue], psID, pubA, pubB, nonceA, nonceB]
        return SessionCrypto.sha256(parts.flatMap { $0 })
    }

    /// Returns `(PS, confirm_key)`.
    public static func derivePairing(dh: [UInt8], oobSalt: [UInt8], transcriptHash th: [UInt8]) -> (secret: [UInt8], confirmKey: [UInt8]) {
        let okm = SessionCrypto.hkdf(salt: oobSalt, ikm: dh, info: ascii("OPENPATCH/1 pairing") + th, length: 64)
        return (Array(okm[0..<32]), Array(okm[32..<64]))
    }

    /// Returns the session keys and `confirm_key`.
    public static func deriveSession(dh: [UInt8], pairingSecret: [UInt8], transcriptHash th: [UInt8]) -> (keys: SessionKeys, confirmKey: [UInt8]) {
        let okm = SessionCrypto.hkdf(salt: pairingSecret, ikm: dh, info: ascii("OPENPATCH/1 session") + th, length: 68)
        return (SessionKeys(keyC2P: Array(okm[0..<16]), keyP2C: Array(okm[16..<32]), salt: Array(okm[32..<36])), Array(okm[36..<68]))
    }

    public static func confirmTag(confirmKey: [UInt8], side: Side, transcriptHash th: [UInt8]) -> [UInt8] {
        let label = side == .pod ? "OPENPATCH/1 confirm pod" : "OPENPATCH/1 confirm app"
        return Array(SessionCrypto.hmacSHA256(key: confirmKey, message: ascii(label) + th).prefix(confirmLength))
    }

    // MARK: Initiator

    /// One handshake run. `random` must return cryptographically secure bytes (the secret is drawn first, then the nonce).
    public final class Initiator {
        public let mode: Mode
        private let secret: [UInt8]
        private let pubA: [UInt8]
        private let nonceA: [UInt8]
        private let pairingSecret: [UInt8]?
        private let oobSalt: [UInt8]
        private var outcome: Outcome?

        /// Pairing handshake; `oob` empty = no out-of-band code.
        public init(pairingWithOOB oob: [UInt8] = [], random: (Int) -> [UInt8]) throws {
            mode = .pair
            secret = random(32)
            nonceA = random(SessionHandshake.nonceLength)
            pubA = try SessionCrypto.x25519KeyPair(secret: secret).publicKey
            pairingSecret = nil
            oobSalt = SessionHandshake.oobSalt(oob)
        }

        /// Session handshake with the stored pairing secret.
        public init(sessionWith pairingSecret: [UInt8], random: (Int) -> [UInt8]) throws {
            precondition(pairingSecret.count == SessionHandshake.pairingSecretLength)
            mode = .session
            secret = random(32)
            nonceA = random(SessionHandshake.nonceLength)
            pubA = try SessionCrypto.x25519KeyPair(secret: secret).publicKey
            self.pairingSecret = pairingSecret
            oobSalt = []
        }

        private var id: [UInt8] { pairingSecret.map(SessionHandshake.psID) ?? [UInt8](repeating: 0, count: SessionHandshake.psIDLength) }
        private var initType: UInt8 { mode == .pair ? FrameType.pairInit : FrameType.sessionInit }
        private var finishType: UInt8 { mode == .pair ? FrameType.pairFinish : FrameType.sessionFinish }

        public func initFrame(seq: UInt16 = 0) -> Data {
            var tlvs = [V1.TLV(tag: Tag.ephPub, value: pubA), V1.TLV(tag: Tag.nonce, value: nonceA)]
            if mode == .session { tlvs.append(V1.TLV(tag: Tag.psID, value: id)) }
            return V1.encode(V1.Message(type: initType, seq: seq, tlvs: tlvs))
        }

        /// Verifies the pod's INIT response and returns the FINISH request.
        public func finishFrame(initResponse: Data, seq: UInt16 = 1) throws -> Data {
            guard let message = try? V1.decode(initResponse), message.type == initType | V1.responseFlag, message.isResponse else { throw Failure.malformed }
            switch message.result {
            case .some(.ok): break
            case .some(let code): throw Failure.rejected(code.rawValue)
            case .none: throw Failure.malformed
            }
            func field(_ tag: UInt8, _ count: Int) throws -> [UInt8] {
                guard let v = message.tlvs.first(where: { $0.tag == tag })?.value, v.count == count else { throw Failure.malformed }
                return v
            }
            let pubB = try field(Tag.ephPub, SessionHandshake.publicKeyLength)
            let nonceB = try field(Tag.nonce, SessionHandshake.nonceLength)
            let confirmB = try field(Tag.confirm, SessionHandshake.confirmLength)
            guard let dh = SessionCrypto.x25519(secret: secret, peer: pubB) else { throw Failure.lowOrderPoint }
            let th = SessionHandshake.transcriptHash(mode: mode, psID: id, pubA: pubA, pubB: pubB, nonceA: nonceA, nonceB: nonceB)
            let confirmKey: [UInt8]
            let result: Outcome
            switch mode {
            case .pair:
                let d = SessionHandshake.derivePairing(dh: dh, oobSalt: oobSalt, transcriptHash: th)
                confirmKey = d.confirmKey; result = .paired(secret: d.secret)
            case .session:
                let d = SessionHandshake.deriveSession(dh: dh, pairingSecret: pairingSecret ?? [], transcriptHash: th)
                confirmKey = d.confirmKey; result = .session(d.keys)
            }
            guard SessionCrypto.constantTimeEqual(confirmB, SessionHandshake.confirmTag(confirmKey: confirmKey, side: .pod, transcriptHash: th)) else {
                throw Failure.badConfirmation
            }
            outcome = result
            let confirmA = SessionHandshake.confirmTag(confirmKey: confirmKey, side: .app, transcriptHash: th)
            return V1.encode(V1.Message(type: finishType, seq: seq, tlvs: [V1.TLV(tag: Tag.confirm, value: confirmA)]))
        }

        /// Checks the pod's FINISH response; `RESULT = OK` yields the outcome to store / install.
        public func complete(finishResponse: Data) throws -> Outcome {
            guard let message = try? V1.decode(finishResponse), message.type == finishType | V1.responseFlag, message.isResponse else { throw Failure.malformed }
            switch message.result {
            case .some(.ok): guard let outcome else { throw Failure.malformed }; return outcome
            case .some(let code): throw Failure.rejected(code.rawValue)
            case .none: throw Failure.malformed
            }
        }
    }
}

/// Encrypts commands and decrypts responses / notifications of one session (docs/04-protocol.md section 6).
/// Frame format, AAD (the 7 header bytes) and nonce `salt(4) | dir(1) | seq(2, LE) | 6 x 0` as in protocol v1 section 5.1;
/// `dir` 0 = commands (key C2P), 1 = responses and 2 = notifications (key P2C).
public final class SecureChannel {
    public let keys: SessionHandshake.SessionKeys
    private let c2p: SessionCrypto.AESCCM
    private let p2c: SessionCrypto.AESCCM
    /// Frame type of unsolicited notifications on the Alert characteristic (nonce direction 2).
    public static let notificationType: UInt8 = 0x90

    public enum Failure: Error, Equatable { case notEncrypted, authentication, malformed }

    public init(keys: SessionHandshake.SessionKeys) {
        self.keys = keys
        c2p = SessionCrypto.AESCCM(key: keys.keyC2P)
        p2c = SessionCrypto.AESCCM(key: keys.keyP2C)
    }

    private func nonce(dir: UInt8, seq: UInt16) -> [UInt8] {
        let counter: [UInt8] = [dir, UInt8(seq & 0xFF), UInt8(seq >> 8)]
        let padding = [UInt8](repeating: 0, count: 6)
        return keys.salt + counter + padding
    }

    private static func finish(header: [UInt8], body: [UInt8]) -> Data {
        var bytes = header + body
        let crc = V1.crc16(bytes)
        bytes.append(UInt8(crc & 0xFF)); bytes.append(UInt8(crc >> 8))
        return Data(bytes)
    }

    /// Seals a command (flags: encrypted). The message's own flags are ignored.
    public func seal(_ message: V1.Message) -> Data {
        let payload = message.tlvs.flatMap { [$0.tag, UInt8($0.value.count)] + $0.value }
        let bodyLength = payload.count + SessionCrypto.AESCCM.tagLength
        precondition(V1.headerSize + bodyLength + V1.crcSize <= V1.maxFrameSize, "frame too large")
        let header: [UInt8] = [V1.version, message.type, V1.flagEncrypted, UInt8(message.seq & 0xFF), UInt8(message.seq >> 8),
                               UInt8(bodyLength & 0xFF), UInt8(bodyLength >> 8)]
        let sealed = c2p.seal(nonce: nonce(dir: 0, seq: message.seq), aad: header, plaintext: payload)
        return Self.finish(header: header, body: sealed)
    }

    /// Opens a response (RESPONSE flag, dir 1) or a notification (type 0x90, dir 2). Commands are not accepted here.
    public func open(_ data: Data) throws -> V1.Message {
        let bytes = [UInt8](data)
        guard bytes.count >= V1.headerSize + V1.crcSize, bytes.count <= V1.maxFrameSize else { throw Failure.malformed }
        let length = Int(bytes[5]) | Int(bytes[6]) << 8
        guard bytes.count == V1.headerSize + length + V1.crcSize else { throw Failure.malformed }
        let stored = UInt16(bytes[bytes.count - 2]) | UInt16(bytes[bytes.count - 1]) << 8
        guard V1.crc16(bytes[0..<(bytes.count - V1.crcSize)]) == stored, bytes[0] == V1.version else { throw Failure.malformed }
        let flags = bytes[2]
        guard flags & V1.flagEncrypted != 0 else { throw Failure.notEncrypted }
        guard flags & V1.flagResponse != 0 else { throw Failure.malformed }   // a command is never a valid inbound frame
        let type = bytes[1]
        let seq = UInt16(bytes[3]) | UInt16(bytes[4]) << 8
        let dir: UInt8 = type == Self.notificationType ? 2 : 1
        let sealed = Array(bytes[V1.headerSize..<(V1.headerSize + length)])
        guard let plain = p2c.open(nonce: nonce(dir: dir, seq: seq), aad: Array(bytes[0..<V1.headerSize]), sealed: sealed) else {
            throw Failure.authentication
        }
        return V1.Message(type: type, flags: flags, seq: seq, tlvs: try V1.parseTLVs(plain))
    }
}
