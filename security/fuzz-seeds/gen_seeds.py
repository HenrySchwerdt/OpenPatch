#!/usr/bin/env python3
"""Generate the small committed fuzz seed corpora under firmware-rs/fuzz/corpus/<target>/.

Seeds are valid inputs (frames, handshake messages, a signed manifest) so libFuzzer starts past the CRC / length checks.
Sources: docs/vectors/session-key-agreement.json (shared Rust/Swift test vectors) and hand-built frames.
Usage: python3 -I security/fuzz-seeds/gen_seeds.py [vectors.json] [corpus_dir]
"""
import hashlib
import json
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
VEC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "docs", "vectors", "session-key-agreement.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "firmware-rs", "fuzz", "corpus")
h = bytes.fromhex


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def frame(type_, flags, seq, payload: bytes) -> bytes:
    body = bytes([1, type_, flags]) + struct.pack("<HH", seq, len(payload)) + payload
    return body + struct.pack("<H", crc16(body))


def tlv(*items) -> bytes:
    return b"".join(bytes([t, len(v)]) + v for t, v in items)


def put(target, name, data: bytes):
    d = os.path.join(OUT, target)
    os.makedirs(d, exist_ok=True)
    open(os.path.join(d, name), "wb").write(data)


def main():
    v = json.load(open(VEC))
    frames = []
    for run in v["pairing"] + [v["session"]]:
        for k, hexs in run["frames"].items():
            frames.append(("hs_%s_%s" % (run["mode"], k), h(hexs)))
    for t in v["traffic"]:
        frames.append(("traffic_" + t["name"].replace(" ", "_"), h(t["frame"])))
    # hand-built plaintext command frames for the codecs
    cmds = {
        "get_status": (0x01, b""),
        "bolus": (0x05, tlv((0x05, struct.pack("<I", 1000)))),
        "temp_basal": (0x03, tlv((0x03, struct.pack("<H", 1000)), (0x04, struct.pack("<H", 60)))),
        "basal": (0x02, tlv((0x02, bytes([0, 0xE8, 0x03])), (0x02, bytes([24, 0xD0, 0x07])))),
        "history": (0x0B, tlv((0x0A, struct.pack("<I", 0)), (0x0B, bytes([10])))),
        "fill_draw": (0x0F, tlv((0x06, struct.pack("<I", 20000)))),
    }
    for n, (t, p) in cmds.items():
        frames.append(("cmd_" + n, frame(t, 0, 7, p)))
    for n, data in frames:
        put("frame_tlv", n, data)
        put("session_open", n, struct.pack("<I", len(data)) + data)  # Vec<Vec<u8>> in `arbitrary` encoding is fuzzer-defined; any bytes are fine
    for n, data in frames:
        if n.startswith("hs_"):
            put("handshake_responder", n, data)
    # structure-aware inputs (arbitrary derives read fixed-size prefixes first)
    for i in range(4):
        put("handshake_mutate", "run%d" % i, bytes([i * 17 + 1] * 32) + bytes(range(8)) + bytes([i, 0, 1, 0, 0x55]))
    put("ccm_open", "zeros", bytes(64))
    put("ccm_open", "ramp", bytes(range(64)) * 2)
    # DFU manifest: header only + a plausible signed shape (signature bytes arbitrary)
    man = struct.pack("<IHHI", 0x5746504F, 1, 0, 4096) + bytes(range(64))
    put("dfu_manifest", "manifest_shape", man + bytes(64))
    put("dfu_manifest", "short", man[:20])
    # storage: valid calibration records (NFP-608-26.45 15:12 etc. are produced by the target from presets; seed = raw layout)
    rec = struct.pack("<IHHHHIII", 0x4F504443, 1, 20, 4, 0, 1000, 1, 0)
    put("storage_records", "cal_shape", rec + bytes([4]))
    print("seeds written to", OUT, "- files:", sum(len(f) for _, _, f in os.walk(OUT)))


main()
