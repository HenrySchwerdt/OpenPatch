import Foundation
#if canImport(CryptoKit)
import CryptoKit
#else
import Crypto
#endif

/// Crypto building blocks of the application layer security (docs/04-protocol.md section 2).
///
/// X25519, SHA-256 and HMAC come from CryptoKit (Apple) or swift-crypto (Linux, same API). HKDF is written out
/// on top of HMAC (RFC 5869, a few lines, checked against the RFC vector) so that Extract and Expand with an
/// explicit PRK behave identically on both libraries. AES-128-CCM (M = 8, L = 2) is implemented here because
/// neither library exposes CCM; the AES block function is a plain software implementation (no constant-time
/// guarantee, acceptable on the phone: the attacker would need to run code on it).
public enum SessionCrypto {
    // MARK: SHA-256 / HMAC / HKDF

    public static func sha256(_ data: [UInt8]) -> [UInt8] { Array(SHA256.hash(data: data)) }

    public static func hmacSHA256(key: [UInt8], message: [UInt8]) -> [UInt8] {
        Array(HMAC<SHA256>.authenticationCode(for: message, using: SymmetricKey(data: key)))
    }

    /// HKDF-Extract (RFC 5869 2.2): `PRK = HMAC(salt, ikm)`. An empty salt means 32 zero bytes.
    public static func hkdfExtract(salt: [UInt8], ikm: [UInt8]) -> [UInt8] {
        hmacSHA256(key: salt.isEmpty ? [UInt8](repeating: 0, count: 32) : salt, message: ikm)
    }

    /// HKDF-Expand (RFC 5869 2.3).
    public static func hkdfExpand(prk: [UInt8], info: [UInt8], length: Int) -> [UInt8] {
        precondition(length <= 255 * 32)
        var okm: [UInt8] = []
        var previous: [UInt8] = []
        var counter: UInt8 = 1
        while okm.count < length {
            previous = hmacSHA256(key: prk, message: previous + info + [counter])
            okm += previous
            counter += 1
        }
        return Array(okm.prefix(length))
    }

    public static func hkdf(salt: [UInt8], ikm: [UInt8], info: [UInt8], length: Int) -> [UInt8] {
        hkdfExpand(prk: hkdfExtract(salt: salt, ikm: ikm), info: info, length: length)
    }

    /// Constant time comparison.
    public static func constantTimeEqual(_ a: [UInt8], _ b: [UInt8]) -> Bool {
        guard a.count == b.count else { return false }
        var diff: UInt8 = 0
        for i in 0..<a.count { diff |= a[i] ^ b[i] }
        return diff == 0
    }

    // MARK: X25519

    public struct KeyPair {
        public let secret: [UInt8]
        public let publicKey: [UInt8]
    }

    /// X25519 key pair from 32 secret bytes (clamping is done by the library).
    public static func x25519KeyPair(secret: [UInt8]) throws -> KeyPair {
        let key = try Curve25519.KeyAgreement.PrivateKey(rawRepresentation: secret)
        return KeyPair(secret: secret, publicKey: Array(key.publicKey.rawRepresentation))
    }

    /// X25519 shared secret; `nil` for a malformed or low-order peer key (all-zero result), which must abort the handshake.
    public static func x25519(secret: [UInt8], peer: [UInt8]) -> [UInt8]? {
        guard let priv = try? Curve25519.KeyAgreement.PrivateKey(rawRepresentation: secret),
              let pub = try? Curve25519.KeyAgreement.PublicKey(rawRepresentation: peer),
              let shared = try? priv.sharedSecretFromKeyAgreement(with: pub) else { return nil }
        let bytes = shared.withUnsafeBytes { Array($0) }
        return bytes.contains(where: { $0 != 0 }) ? bytes : nil
    }

    // MARK: AES-128

    /// AES-128 block encryption (FIPS 197), software implementation.
    public struct AES128 {
        private static let sbox: [UInt8] = {
            var box = [UInt8](repeating: 0, count: 256)
            var p: UInt8 = 1, q: UInt8 = 1
            repeat {
                p = p ^ (p << 1) ^ ((p & 0x80) != 0 ? 0x1B : 0)           // p *= 3 in GF(2^8)
                q ^= q << 1; q ^= q << 2; q ^= q << 4                      // q /= 3
                if q & 0x80 != 0 { q ^= 0x09 }
                func rotl(_ v: UInt8, _ n: UInt8) -> UInt8 { (v << n) | (v >> (8 - n)) }
                box[Int(p)] = q ^ rotl(q, 1) ^ rotl(q, 2) ^ rotl(q, 3) ^ rotl(q, 4) ^ 0x63
            } while p != 1
            box[0] = 0x63
            return box
        }()

        private let roundKeys: [[UInt8]]

        public init(key: [UInt8]) {
            precondition(key.count == 16, "AES-128 key must be 16 bytes")
            var w = key
            var rcon: UInt8 = 1
            var keys: [[UInt8]] = [key]
            for _ in 1...10 {
                var t = Array(w[12..<16])
                t = [Self.sbox[Int(t[1])] ^ rcon, Self.sbox[Int(t[2])], Self.sbox[Int(t[3])], Self.sbox[Int(t[0])]]
                rcon = (rcon << 1) ^ ((rcon & 0x80) != 0 ? 0x1B : 0)
                var next = [UInt8](repeating: 0, count: 16)
                for i in 0..<4 { next[i] = w[i] ^ t[i] }
                for i in 4..<16 { next[i] = w[i] ^ next[i - 4] }
                keys.append(next)
                w = next
            }
            roundKeys = keys
        }

        private static func xtime(_ x: UInt8) -> UInt8 { (x << 1) ^ ((x & 0x80) != 0 ? 0x1B : 0) }

        public func encrypt(block: [UInt8]) -> [UInt8] {
            precondition(block.count == 16)
            var s = zip(block, roundKeys[0]).map { $0 ^ $1 }
            for round in 1...10 {
                s = s.map { Self.sbox[Int($0)] }
                // ShiftRows (column-major state: s[4 * column + row])
                var shifted = s
                for c in 0..<4 { for r in 0..<4 { shifted[4 * c + r] = s[4 * ((c + r) % 4) + r] } }
                s = shifted
                if round != 10 {
                    var mixed = s
                    for c in 0..<4 {
                        let a = Array(s[4 * c..<4 * c + 4])
                        let all = a[0] ^ a[1] ^ a[2] ^ a[3]
                        for r in 0..<4 { mixed[4 * c + r] = a[r] ^ all ^ Self.xtime(a[r] ^ a[(r + 1) % 4]) }
                    }
                    s = mixed
                }
                s = zip(s, roundKeys[round]).map { $0 ^ $1 }
            }
            return s
        }
    }

    // MARK: AES-128-CCM (RFC 3610, M = 8, L = 2, 13 byte nonce)

    public struct AESCCM {
        public static let tagLength = 8
        public static let nonceLength = 13
        private let aes: AES128

        public init(key: [UInt8]) { aes = AES128(key: key) }

        private func xor(_ a: [UInt8], _ b: ArraySlice<UInt8>) -> [UInt8] { zip(a, b).map { $0 ^ $1 } }

        /// CBC-MAC over B0 | encoded AAD | message, tag = first 8 bytes.
        private func mac(nonce: [UInt8], aad: [UInt8], message: [UInt8]) -> [UInt8] {
            var b0 = [UInt8](repeating: 0, count: 16)
            b0[0] = (aad.isEmpty ? 0 : 0x40) | UInt8(((Self.tagLength - 2) / 2) << 3) | 1   // L - 1 = 1
            b0.replaceSubrange(1..<14, with: nonce)
            b0[14] = UInt8(message.count >> 8); b0[15] = UInt8(message.count & 0xFF)
            var x = aes.encrypt(block: b0)
            var blob: [UInt8] = []
            if !aad.isEmpty {
                precondition(aad.count < 0xFF00)
                blob = [UInt8(aad.count >> 8), UInt8(aad.count & 0xFF)] + aad
                blob += [UInt8](repeating: 0, count: (16 - blob.count % 16) % 16)
            }
            blob += message
            blob += [UInt8](repeating: 0, count: (16 - blob.count % 16) % 16)
            for i in stride(from: 0, to: blob.count, by: 16) { x = aes.encrypt(block: xor(x, blob[i..<i + 16])) }
            return Array(x.prefix(Self.tagLength))
        }

        private func keystream(nonce: [UInt8], counter: UInt16) -> [UInt8] {
            var a = [UInt8](repeating: 0, count: 16)
            a[0] = 1   // L - 1
            a.replaceSubrange(1..<14, with: nonce)
            a[14] = UInt8(counter >> 8); a[15] = UInt8(counter & 0xFF)
            return aes.encrypt(block: a)
        }

        private func crypt(nonce: [UInt8], data: [UInt8]) -> [UInt8] {
            var out = [UInt8](); out.reserveCapacity(data.count)
            var counter: UInt16 = 1
            for i in stride(from: 0, to: data.count, by: 16) {
                let ks = keystream(nonce: nonce, counter: counter)
                let chunk = data[i..<min(i + 16, data.count)]
                out += zip(chunk, ks).map { $0 ^ $1 }
                counter += 1
            }
            return out
        }

        /// Returns `ciphertext || tag`.
        public func seal(nonce: [UInt8], aad: [UInt8], plaintext: [UInt8]) -> [UInt8] {
            precondition(nonce.count == Self.nonceLength)
            let t = mac(nonce: nonce, aad: aad, message: plaintext)
            let s0 = keystream(nonce: nonce, counter: 0)
            return crypt(nonce: nonce, data: plaintext) + zip(t, s0).map { $0 ^ $1 }
        }

        /// Input `ciphertext || tag`; `nil` when the tag does not verify.
        public func open(nonce: [UInt8], aad: [UInt8], sealed: [UInt8]) -> [UInt8]? {
            guard nonce.count == Self.nonceLength, sealed.count >= Self.tagLength else { return nil }
            let ct = Array(sealed.dropLast(Self.tagLength))
            let tag = Array(sealed.suffix(Self.tagLength))
            let plaintext = crypt(nonce: nonce, data: ct)
            let expected = zip(mac(nonce: nonce, aad: aad, message: plaintext), keystream(nonce: nonce, counter: 0)).map { $0 ^ $1 }
            return SessionCrypto.constantTimeEqual(expected, tag) ? plaintext : nil
        }
    }
}
