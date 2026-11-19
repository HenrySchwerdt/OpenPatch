import OpenPatchCore
import XCTest
@testable import OpenPatchKit

/// A pod with the application layer security of docs/04-protocol.md (a second implementation from the same primitives, the byte
/// level agreement with the Rust pod is proven in `OpenPatchCoreTests/SessionHandshakeTests`). Answers every command with OK.
private final class SecurePodLink: FrameLink {
    var isConnected = true
    var pairingWindowOpen = false
    var pairingSecret: [UInt8]?
    var plainFrames = 0, encryptedFrames = 0, handshakes: [UInt8] = []
    private enum Pending { case pair(secret: [UInt8], confirmKey: [UInt8], th: [UInt8]), session(keys: SessionHandshake.SessionKeys, confirmKey: [UInt8], th: [UInt8]) }
    private var pending: Pending?
    private var active: (keys: SessionHandshake.SessionKeys, c2p: SessionCrypto.AESCCM, p2c: SessionCrypto.AESCCM)?
    private var counter: UInt8 = 0x40

    func connect(completion: @escaping (Result<Void, TransportError>) -> Void) { isConnected = true; active = nil; pending = nil; completion(.success(())) }
    func disconnect() { isConnected = false; active = nil; pending = nil }
    private func draw(_ n: Int) -> [UInt8] { (0..<n).map { _ in counter = counter &* 37 &+ 11; return counter } }
    private func reply(_ type: UInt8, seq: UInt16, _ tlvs: [V1.TLV]) -> Data { V1.encode(V1.Message(type: type | V1.responseFlag, flags: V1.flagResponse, seq: seq, tlvs: tlvs)) }
    private func result(_ type: UInt8, seq: UInt16, _ r: V1.Result) -> Data { reply(type, seq: seq, [V1.TLV(.result, u8: r.rawValue)]) }

    func exchange(frame: Data, seq: UInt16, completion: @escaping (Result<Data, TransportError>) -> Void) {
        let bytes = [UInt8](frame)
        let type = bytes[1]
        if (SessionHandshake.FrameType.pairInit...SessionHandshake.FrameType.sessionFinish).contains(type) {
            handshakes.append(type)
            return completion(.success(handshake(type: type, seq: seq, message: try! V1.decode(frame))))
        }
        guard bytes[2] & V1.flagEncrypted != 0 else { plainFrames += 1; return completion(.failure(.timeout)) }   // a production pod ignores plaintext
        guard let active else { return completion(.failure(.timeout)) }
        encryptedFrames += 1
        let nonce = active.keys.salt + [0, UInt8(seq & 0xFF), UInt8(seq >> 8)] + [UInt8](repeating: 0, count: 6)
        guard active.c2p.open(nonce: nonce, aad: Array(bytes[0..<V1.headerSize]), sealed: Array(bytes[V1.headerSize..<(bytes.count - V1.crcSize)])) != nil else {
            return completion(.failure(.timeout))
        }
        let payload: [UInt8] = [V1.Tag.result.rawValue, 1, 0]
        let header: [UInt8] = [1, type | V1.responseFlag, V1.flagEncrypted | V1.flagResponse, UInt8(seq & 0xFF), UInt8(seq >> 8), UInt8(payload.count + 8), 0]
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
            return reply(type, seq: seq, [V1.TLV(.result, u8: 0), V1.TLV(tag: SessionHandshake.Tag.ephPub, value: pubB),
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
                  SessionCrypto.constantTimeEqual(tag, SessionHandshake.confirmTag(confirmKey: want.ck, side: .app, transcriptHash: want.th)) else { return result(type, seq: seq, .auth) }
            switch pending {
            case .pair(let secret, _, _): pairingSecret = secret; pairingWindowOpen = false
            case .session(let keys, _, _): active = (keys, SessionCrypto.AESCCM(key: keys.keyC2P), SessionCrypto.AESCCM(key: keys.keyP2C))
            case nil: break
            }
            return result(type, seq: seq, .ok)
        }
    }
}

/// Pairing secret in the keychain store, the session wired into the transport the manager builds.
final class OpenPatchPairingTests: XCTestCase {
    private var link: SecurePodLink!
    private var store: InMemoryPairingSecretStore!
    private var savedFactory: ((OpenPatchPumpManagerState) -> OpenPatchTransport)!
    private var savedStore: PairingSecretStore!
    private let pod = UUID()

    override func setUp() {
        super.setUp()
        link = SecurePodLink()
        store = InMemoryPairingSecretStore()
        savedFactory = OpenPatchPumpManager.transportFactory
        savedStore = OpenPatchPumpManager.pairingSecretStore
        OpenPatchPumpManager.uncertaintyRecoveryDelays = []
        OpenPatchPumpManager.pairingSecretStore = store
        OpenPatchPumpManager.transportFactory = { [unowned self] state in OpenPatchPumpManager.makeV1Transport(state: state, link: self.link) }
    }

    override func tearDown() {
        OpenPatchPumpManager.transportFactory = savedFactory
        OpenPatchPumpManager.pairingSecretStore = savedStore
        super.tearDown()
    }

    private func newManager() -> OpenPatchPumpManager {
        var state = OpenPatchPumpManagerState()
        state.peripheralIdentifier = pod
        return OpenPatchPumpManager(state: state)
    }

    private func pair(_ manager: OpenPatchPumpManager) -> Error? {
        var result: Error?
        let done = expectation(description: "pair")
        manager.pair(peripheralIdentifier: pod, name: "OpenPatch-1234", simulated: false) { result = $0; done.fulfill() }
        wait(for: [done], timeout: 5)
        return result
    }

    func test_pairing_createsTheSecretOnceInTheStore_andEverythingAfterwardsIsEncrypted() {
        link.pairingWindowOpen = true
        let manager = newManager()
        _ = pair(manager)    // the status carries no drive calibration: the pairing itself is what this test is about
        let stored = store.secret(for: pod.uuidString)
        XCTAssertEqual(stored, link.pairingSecret, "the secret in the store is the one the pod holds")
        XCTAssertEqual(stored?.count, 32)
        XCTAssertEqual(link.handshakes, [SessionHandshake.FrameType.pairInit, SessionHandshake.FrameType.pairFinish,
                                         SessionHandshake.FrameType.sessionInit, SessionHandshake.FrameType.sessionFinish], "pair, then the first command opens a session")
        XCTAssertGreaterThan(link.encryptedFrames, 0)
        XCTAssertEqual(link.plainFrames, 0, "not one command went out in plain text")
        XCTAssertTrue(manager.isPodPaired)
        XCTAssertTrue(manager.hasSecureSession)
        XCTAssertFalse(String(describing: manager.rawState).contains(stored.map { $0.map { String(format: "%02x", $0) }.joined() } ?? "?"), "the secret is never part of rawState")
    }

    func test_aSecondRun_usesTheStoredSecret_andNeverPairsAgain() {
        link.pairingWindowOpen = true
        _ = pair(newManager())
        link.handshakes = []
        let again = newManager()                     // app restart: new manager, same keychain
        XCTAssertTrue(again.isPodPaired)
        var result: Error?
        let done = expectation(description: "status")
        again.refreshStatus { result = $0; done.fulfill() }
        wait(for: [done], timeout: 5)
        XCTAssertNil(result)
        XCTAssertEqual(link.handshakes, [SessionHandshake.FrameType.sessionInit, SessionHandshake.FrameType.sessionFinish])
        XCTAssertTrue(again.hasSecureSession)
    }

    func test_pairingWithTheWindowClosed_asksForTheButton_andStoresNothing() {
        link.pairingWindowOpen = false
        let error = pair(newManager())
        XCTAssertEqual(error as? OpenPatchError, .needsPairing)
        XCTAssertNil(store.secret(for: pod.uuidString))
        XCTAssertEqual(link.encryptedFrames, 0)
    }

    func test_aPodThatWasResetOrPairedByAnotherPhone_isPairedAgainAutomatically_ifItsWindowIsOpen() {
        link.pairingWindowOpen = true
        _ = pair(newManager())
        let old = store.secret(for: pod.uuidString)
        link.pairingSecret = nil                         // the pod was reset
        link.pairingWindowOpen = true                    // the user pressed its button
        link.handshakes = []
        _ = pair(newManager())
        XCTAssertNotNil(store.secret(for: pod.uuidString))
        XCTAssertNotEqual(store.secret(for: pod.uuidString), old, "a new secret replaced the stale one")
        XCTAssertEqual(store.secret(for: pod.uuidString), link.pairingSecret)
    }

    func test_aResetPodWithItsWindowClosed_reportsThatPairingIsNeeded() {
        link.pairingWindowOpen = true
        _ = pair(newManager())
        link.pairingSecret = nil
        link.pairingWindowOpen = false
        let error = pair(newManager())
        XCTAssertEqual(error as? OpenPatchError, .needsPairing)
        XCTAssertNil(store.secret(for: pod.uuidString), "the stale secret is forgotten")
    }

    func test_simulatedPodsNeedNoSecret_andUseNoKeychain() {
        var state = OpenPatchPumpManagerState()
        state.usesSimulatedPod = true
        state.peripheralIdentifier = pod
        XCTAssertNil(OpenPatchPumpManager.podKey(for: state))
    }

    func test_theKeychainStore_roundTrips_whenTheEnvironmentAllowsKeychainAccess() throws {
        let keychain = KeychainPairingSecretStore(service: "org.openpatch.test.\(UUID().uuidString)")
        let key = UUID().uuidString
        do { try keychain.save([UInt8](repeating: 7, count: 32), for: key) } catch let error as PairingSecretStoreError {
            throw XCTSkip("keychain not available in this test host (OSStatus \(error.status))")
        }
        defer { keychain.remove(for: key) }
        XCTAssertEqual(keychain.secret(for: key), [UInt8](repeating: 7, count: 32))
        try keychain.save([UInt8](repeating: 9, count: 32), for: key)
        XCTAssertEqual(keychain.secret(for: key), [UInt8](repeating: 9, count: 32), "update in place")
        keychain.remove(for: key)
        XCTAssertNil(keychain.secret(for: key))
    }
}
