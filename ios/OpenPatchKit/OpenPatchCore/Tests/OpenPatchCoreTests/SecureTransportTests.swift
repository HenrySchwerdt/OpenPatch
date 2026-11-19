import XCTest
@testable import OpenPatchCore

/// A pod that speaks the application layer security of docs/04-protocol.md, built from the same primitives (a second
/// implementation next to the Rust pod; the byte-level agreement with Rust is proven by `SessionHandshakeTests`).
private final class SecurePodLink: FrameLink {
    var isConnected = true
    var pairingWindowOpen = false
    var pairingSecret: [UInt8]?
    /// Every frame the phone sent, in order.
    var wire: [Data] = []
    /// Decrypted command seqs and types of the current and earlier sessions.
    var commands: [(type: UInt8, seq: UInt16)] = []
    var repliesInPlaintext = false
    private(set) var sessionKeys: [SessionHandshake.SessionKeys] = []

    private enum Pending {
        case pair(secret: [UInt8], confirmKey: [UInt8], th: [UInt8])
        case session(keys: SessionHandshake.SessionKeys, confirmKey: [UInt8], th: [UInt8])
    }
    private var pending: Pending?
    private var active: (keys: SessionHandshake.SessionKeys, c2p: SessionCrypto.AESCCM, p2c: SessionCrypto.AESCCM)?
    private var counter: UInt8 = 0x40

    func connect(completion: @escaping (Result<Void, TransportError>) -> Void) { isConnected = true; active = nil; pending = nil; completion(.success(())) }
    func disconnect() { isConnected = false; active = nil; pending = nil }

    private func draw(_ n: Int) -> [UInt8] { (0..<n).map { _ in counter = counter &* 37 &+ 11; return counter } }

    private func response(_ type: UInt8, seq: UInt16, _ tlvs: [V1.TLV]) -> Data {
        V1.encode(V1.Message(type: type | V1.responseFlag, flags: V1.flagResponse, seq: seq, tlvs: tlvs))
    }
    private func result(_ type: UInt8, seq: UInt16, _ r: V1.Result) -> Data { response(type, seq: seq, [V1.TLV(.result, u8: r.rawValue)]) }

    func exchange(frame: Data, seq: UInt16, completion: @escaping (Result<Data, TransportError>) -> Void) {
        wire.append(frame)
        let bytes = [UInt8](frame)
        let type = bytes[1]
        if (SessionHandshake.FrameType.pairInit...SessionHandshake.FrameType.sessionFinish).contains(type) {
            return completion(.success(handshake(type: type, seq: seq, message: try! V1.decode(frame))))
        }
        guard bytes[2] & V1.flagEncrypted != 0, let active else { return completion(.failure(.timeout)) }   // pod refuses silently
        let nonce = active.keys.salt + [0, UInt8(seq & 0xFF), UInt8(seq >> 8)] + [UInt8](repeating: 0, count: 6)
        let body = Array(bytes[V1.headerSize..<(bytes.count - V1.crcSize)])
        guard active.c2p.open(nonce: nonce, aad: Array(bytes[0..<V1.headerSize]), sealed: body) != nil else { return completion(.failure(.timeout)) }
        commands.append((type, seq))
        let tlvs = [V1.TLV(.result, u8: 0)]
        if repliesInPlaintext { return completion(.success(response(type, seq: seq, tlvs))) }
        let payload = tlvs.flatMap { [$0.tag, UInt8($0.value.count)] + $0.value }
        let len = payload.count + 8
        let header: [UInt8] = [1, type | V1.responseFlag, V1.flagEncrypted | V1.flagResponse, UInt8(seq & 0xFF), UInt8(seq >> 8), UInt8(len), 0]
        let rnonce = active.keys.salt + [1, UInt8(seq & 0xFF), UInt8(seq >> 8)] + [UInt8](repeating: 0, count: 6)
        var out = header + active.p2c.seal(nonce: rnonce, aad: header, plaintext: payload)
        let crc = V1.crc16(out)
        out += [UInt8(crc & 0xFF), UInt8(crc >> 8)]
        completion(.success(Data(out)))
    }

    private func handshake(type: UInt8, seq: UInt16, message: V1.Message) -> Data {
        func field(_ tag: UInt8) -> [UInt8]? { message.tlvs.first { $0.tag == tag }?.value }
        switch type {
        case SessionHandshake.FrameType.pairInit, SessionHandshake.FrameType.sessionInit:
            let pairing = type == SessionHandshake.FrameType.pairInit
            if pairing && !pairingWindowOpen { return result(type, seq: seq, .auth) }
            guard let pubA = field(SessionHandshake.Tag.ephPub), let nonceA = field(SessionHandshake.Tag.nonce) else { return result(type, seq: seq, .frame) }
            var id = [UInt8](repeating: 0, count: 4)
            if !pairing {
                guard let ps = pairingSecret, field(SessionHandshake.Tag.psID) == SessionHandshake.psID(ps) else { return result(type, seq: seq, .pair) }
                id = SessionHandshake.psID(ps)
            }
            let secret = draw(32), nonceB = draw(16)
            let pubB = try! SessionCrypto.x25519KeyPair(secret: secret).publicKey
            guard let dh = SessionCrypto.x25519(secret: secret, peer: pubA) else { return result(type, seq: seq, .badArg) }
            let th = SessionHandshake.transcriptHash(mode: pairing ? .pair : .session, psID: id, pubA: pubA, pubB: pubB, nonceA: nonceA, nonceB: nonceB)
            let ck: [UInt8]
            if pairing {
                let d = SessionHandshake.derivePairing(dh: dh, oobSalt: SessionHandshake.oobSalt([]), transcriptHash: th)
                ck = d.confirmKey; pending = .pair(secret: d.secret, confirmKey: ck, th: th)
            } else {
                let d = SessionHandshake.deriveSession(dh: dh, pairingSecret: pairingSecret!, transcriptHash: th)
                ck = d.confirmKey; pending = .session(keys: d.keys, confirmKey: ck, th: th)
            }
            let confirm = SessionHandshake.confirmTag(confirmKey: ck, side: .pod, transcriptHash: th)
            return response(type, seq: seq, [V1.TLV(.result, u8: 0), V1.TLV(tag: SessionHandshake.Tag.ephPub, value: pubB),
                                             V1.TLV(tag: SessionHandshake.Tag.nonce, value: nonceB), V1.TLV(tag: SessionHandshake.Tag.confirm, value: confirm)])
        default:
            defer { pending = nil }
            let want: (ck: [UInt8], th: [UInt8])
            switch pending {
            case .pair(_, let ck, let th) where type == SessionHandshake.FrameType.pairFinish: want = (ck, th)
            case .session(_, let ck, let th) where type == SessionHandshake.FrameType.sessionFinish: want = (ck, th)
            default: return result(type, seq: seq, .session)
            }
            guard let tag = field(SessionHandshake.Tag.confirm),
                  SessionCrypto.constantTimeEqual(tag, SessionHandshake.confirmTag(confirmKey: want.ck, side: .app, transcriptHash: want.th)) else {
                return result(type, seq: seq, .auth)
            }
            switch pending {
            case .pair(let secret, _, _): pairingSecret = secret; pairingWindowOpen = false
            case .session(let keys, _, _):
                active = (keys, SessionCrypto.AESCCM(key: keys.keyC2P), SessionCrypto.AESCCM(key: keys.keyP2C)); sessionKeys.append(keys)
            case nil: break
            }
            return result(type, seq: seq, .ok)
        }
    }
}

final class SecureTransportTests: XCTestCase {
    private var link: SecurePodLink!
    private var checkpoints: [V1Transport.Checkpoint] = []

    private func makeTransport(secret: [UInt8]? = nil, initialSequence: UInt16 = 1) -> V1Transport {
        let transport = V1Transport(link: link, initialPhase: .active, initialSequence: initialSequence, pairingSecret: secret,
                                    clock: { Date(timeIntervalSince1970: 1_800_000_000) }, timeOfDayMilliseconds: { 43_200_000 })
        transport.checkpointHandler = { [unowned self] in checkpoints.append($0) }
        return transport
    }

    private func send(_ transport: V1Transport, _ command: Command) -> Result<Response, TransportError> {
        var result: Result<Response, TransportError>!
        transport.send(command) { result = $0 }
        return result
    }

    private func pair(_ transport: V1Transport) -> Result<[UInt8], TransportError> {
        var result: Result<[UInt8], TransportError>!
        transport.pair { result = $0 }
        return result
    }

    override func setUp() { link = SecurePodLink(); checkpoints = [] }

    func test_pairing_inTheWindow_createsTheSameSecretOnBothSides_andClosesTheWindow() throws {
        link.pairingWindowOpen = true
        let transport = makeTransport()
        let secret = try pair(transport).get()
        XCTAssertEqual(secret.count, 32)
        XCTAssertEqual(link.pairingSecret, secret)
        XCTAssertFalse(link.pairingWindowOpen)
        XCTAssertEqual(link.wire.map { $0[1] }, [SessionHandshake.FrameType.pairInit, SessionHandshake.FrameType.pairFinish])
    }

    func test_pairing_outsideTheWindow_isRefused_andNothingIsStored() {
        let transport = makeTransport()
        XCTAssertEqual(pair(transport), .failure(.sessionFailed))
        XCTAssertNil(link.pairingSecret)
    }

    func test_withPairingSecret_everyCommandIsEncrypted_andTheSequenceRestartsAtOnePerSession() throws {
        link.pairingWindowOpen = true
        let transport = makeTransport(initialSequence: 500)
        _ = try pair(transport).get()
        XCTAssertNotNil(try? send(transport, .getStatus).get())
        XCTAssertEqual(link.wire.map { $0[1] }.prefix(4), [0x40, 0x41, 0x42, 0x43])
        let commandFrames = link.wire.dropFirst(4)
        XCTAssertFalse(commandFrames.isEmpty)
        for frame in commandFrames { XCTAssertEqual(frame[frame.startIndex + 2] & V1.flagEncrypted, V1.flagEncrypted) }
        XCTAssertEqual(link.commands.first?.seq, 1, "the sequence space is per session")
        XCTAssertEqual(link.commands.map { $0.seq }, Array(1...UInt16(link.commands.count)))
        XCTAssertTrue(transport.hasSession)
        XCTAssertEqual(checkpoints.first?.nextSequence, 1)
    }

    func test_reconnect_runsANewHandshake_withFreshKeys_andOldFramesAreUseless() throws {
        link.pairingWindowOpen = true
        let transport = makeTransport()
        let secret = try pair(transport).get()
        _ = try send(transport, .getStatus).get()
        let oldFrame = link.wire.last!
        transport.disconnect()
        XCTAssertFalse(transport.hasSession)
        var connected = false
        transport.connect { _ in connected = true }
        XCTAssertTrue(connected)
        _ = try send(transport, .getStatus).get()
        XCTAssertEqual(link.sessionKeys.count, 2)
        XCTAssertNotEqual(link.sessionKeys[0], link.sessionKeys[1])
        XCTAssertEqual(link.commands.map { $0.seq }, [1, 1], "each session starts again at seq 1")
        // a recorded frame of the first session does not authenticate in the second one
        var replyResult: Result<Data, TransportError>?
        link.exchange(frame: oldFrame, seq: 1) { replyResult = $0 }
        XCTAssertEqual(replyResult, .failure(.timeout))
        XCTAssertEqual(secret.count, 32)
    }

    func test_podWithAnotherPairingSecret_reportsNotPaired_andNoCommandGoesOut() throws {
        link.pairingSecret = [UInt8](repeating: 0x55, count: 32)
        let transport = makeTransport(secret: [UInt8](repeating: 0x66, count: 32))
        XCTAssertEqual(send(transport, .getStatus), .failure(.notPaired))
        XCTAssertEqual(link.wire.map { $0[1] }, [SessionHandshake.FrameType.sessionInit])
        XCTAssertTrue(link.commands.isEmpty)
    }

    func test_unpairedPod_reportsNotPaired() {
        let transport = makeTransport(secret: [UInt8](repeating: 0x66, count: 32))
        XCTAssertEqual(send(transport, .getStatus), .failure(.notPaired))
    }

    func test_withASession_aPlaintextReplyIsNotBelieved() throws {
        link.pairingWindowOpen = true
        let transport = makeTransport()
        _ = try pair(transport).get()
        link.repliesInPlaintext = true
        XCTAssertEqual(send(transport, .getStatus), .failure(.malformedResponse))
    }

    func test_withoutPairingSecret_theTransportStaysPlaintextAndRunsNoHandshake() {
        // the simulator / dev-plaintext behaviour is unchanged: a plaintext frame goes out, no handshake frame does
        let transport = makeTransport()
        _ = send(transport, .getStatus)
        XCTAssertEqual(link.wire.count, 1)
        XCTAssertEqual(link.wire[0][2] & V1.flagEncrypted, 0)
    }
}
