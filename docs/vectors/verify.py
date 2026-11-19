#!/usr/bin/env python3
"""Independent check of session-key-agreement.json with the `cryptography` package.

Re-derives every value of docs/04-protocol.md section 5 from the inputs in the file, using none of
the project code (not the Rust, not the Swift implementation), and also builds the handshake frames
and the AES-CCM traffic. Usage: python3 -I docs/vectors/verify.py
"""
import hashlib
import hmac
import json
import os
import sys

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESCCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF, HKDFExpand

HERE = os.path.dirname(os.path.abspath(__file__))
V = json.load(open(os.path.join(HERE, "session-key-agreement.json")))
h = bytes.fromhex


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def frame(type_, flags, seq, payload: bytes) -> bytes:
    body = bytes([1, type_, flags]) + seq.to_bytes(2, "little") + len(payload).to_bytes(2, "little") + payload
    return body + crc16(body).to_bytes(2, "little")


def tlv(*items) -> bytes:
    return b"".join(bytes([t, len(v)]) + v for t, v in items)


def x25519(secret: bytes, peer: bytes) -> bytes:
    return X25519PrivateKey.from_private_bytes(secret).exchange(X25519PublicKey.from_public_bytes(peer))


def pub(secret: bytes) -> bytes:
    return X25519PrivateKey.from_private_bytes(secret).public_key().public_bytes_raw()


def hkdf(salt: bytes, ikm: bytes, info: bytes, n: int) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=n, salt=salt, info=info).derive(ikm)


def hmac16(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()[:16]


ok = True


def check(name, got, want):
    global ok
    if got != want:
        ok = False
        print(f"MISMATCH {name}\n  got  {got.hex() if isinstance(got, bytes) else got}\n  want {want.hex() if isinstance(want, bytes) else want}")


# primitives
p = V["primitives"]["x25519_rfc7748_6_1"]
check("rfc7748 shared", x25519(h(p["alice_secret"]), h(p["bob_public"])), h(p["shared"]))
q = V["primitives"]["hkdf_sha256_rfc5869_a1"]
check("rfc5869", hkdf(h(q["salt"]), h(q["ikm"]), h(q["info"]), q["length"]), h(q["okm"]))
c = V["primitives"]["aes128_ccm_rfc3610_packet_vector_1"]
check("rfc3610", AESCCM(h(c["key"]), tag_length=8).encrypt(h(c["nonce"]), h(c["plaintext"]), h(c["aad"])), h(c["ciphertext"]) + h(c["tag"]))


def case(c):
    mode = 1 if c["mode"] == "pair" else 2
    a_sec, b_sec = h(c["app_eph_secret"]), h(c["pod_eph_secret"])
    a_pub, b_pub = pub(a_sec), pub(b_sec)
    na, nb = h(c["app_nonce"]), h(c["pod_nonce"])
    check("app pub", a_pub, h(c["app_eph_public"]))
    check("pod pub", b_pub, h(c["pod_eph_public"]))
    dh = x25519(a_sec, b_pub)
    check("dh", dh, h(c["dh"]))
    if mode == 1:
        oob = h(c["oob"])
        salt = hashlib.sha256(b"OPENPATCH/1 oob" + oob).digest() if oob else bytes(32)
        ps_id = bytes(4)
    else:
        ps = h(c["ps"])
        ps_id = HKDFExpand(algorithm=hashes.SHA256(), length=4, info=b"OPENPATCH/1 ps-id").derive(ps)
        salt = ps
    check("ps_id", ps_id, h(c["ps_id"]))
    th = hashlib.sha256(b"OPENPATCH/1 transcript" + bytes([mode]) + ps_id + a_pub + b_pub + na + nb).digest()
    check("transcript", th, h(c["transcript_hash"]))
    if mode == 1:
        okm = hkdf(salt, dh, b"OPENPATCH/1 pairing" + th, 64)
        check("ps", okm[:32], h(c["ps"]))
        ck = okm[32:]
    else:
        okm = hkdf(salt, dh, b"OPENPATCH/1 session" + th, 68)
        check("key_c2p", okm[:16], h(c["key_c2p"]))
        check("key_p2c", okm[16:32], h(c["key_p2c"]))
        check("salt", okm[32:36], h(c["salt"]))
        ck = okm[36:]
    check("confirm_key", ck, h(c["confirm_key"]))
    cp, ca = hmac16(ck, b"OPENPATCH/1 confirm pod" + th), hmac16(ck, b"OPENPATCH/1 confirm app" + th)
    check("confirm_pod", cp, h(c["confirm_pod"]))
    check("confirm_app", ca, h(c["confirm_app"]))
    base = 0x40 if mode == 1 else 0x42
    init = tlv((0x30, a_pub), (0x31, na)) + (tlv((0x33, ps_id)) if mode == 2 else b"")
    fr = c["frames"]
    check("init_request", frame(base, 0, 0, init), h(fr["init_request"]))
    check("init_response", frame(base | 0x80, 2, 0, tlv((1, b"\x00"), (0x30, b_pub), (0x31, nb), (0x32, cp))), h(fr["init_response"]))
    check("finish_request", frame(base + 1, 0, 1, tlv((0x32, ca))), h(fr["finish_request"]))
    check("finish_response", frame((base + 1) | 0x80, 2, 1, tlv((1, b"\x00"))), h(fr["finish_response"]))


for c in V["pairing"] + [V["session"]]:
    case(c)

s = V["session"]
check("session ps == pairing[0] ps", h(s["ps"]), h(V["pairing"][0]["ps"]))
for t in V["traffic"]:
    key = h(s["key_c2p"]) if t["dir"] == 0 else h(s["key_p2c"])
    nonce = h(s["salt"]) + bytes([t["dir"]]) + t["seq"].to_bytes(2, "little") + bytes(6)
    flags = 1 | (2 if t["dir"] else 0)
    plain = h(t["payload"])
    hdr = bytes([1, t["type"], flags]) + t["seq"].to_bytes(2, "little") + (len(plain) + 8).to_bytes(2, "little")
    ct = AESCCM(key, tag_length=8).encrypt(nonce, plain, hdr)
    check("traffic " + t["name"], frame(t["type"], flags, t["seq"], ct), h(t["frame"]))

print("vectors verified independently" if ok else "FAILED")
sys.exit(0 if ok else 1)
