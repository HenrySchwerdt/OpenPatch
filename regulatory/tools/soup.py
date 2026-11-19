#!/usr/bin/env python3
"""SOUP list (IEC 62304 5.3.3 / 8.1.2) generated from lock files.

Inputs
  firmware-rs/Cargo.lock                    host workspace (core, proto, differential tests)
  firmware-rs/openpatch-bench/Cargo.lock    embedded bench app (separate workspace)
  firmware-rs/openpatch-bootloader/Cargo.lock
  ios/OpenPatchKit/OpenPatchCore/Package.resolved   Swift packages
  regulatory/SOFTWARE/soup-extra.csv        SOUP that is not in a lock file (binary blobs, OS frameworks, host apps)
  regulatory/SOFTWARE/soup-licences.json    licence cache (crates.io API), refreshed with --fetch-licences

Outputs (default): regulatory/SOFTWARE/SOUP.md and regulatory/SOFTWARE/soup.json
The CycloneDX SBOM for supply-chain security is owned by security/ (not produced here).

Usage
  python3 regulatory/tools/soup.py                    # regenerate SOUP.md / soup.json from the cache
  python3 regulatory/tools/soup.py --fetch-licences   # refresh missing licences from crates.io (1 request/s, polite)
  python3 regulatory/tools/soup.py --check            # CI: fail if the committed soup.json is stale vs the lock files
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT_MD = ROOT / "regulatory/SOFTWARE/SOUP.md"
OUT_JSON = ROOT / "regulatory/SOFTWARE/soup.json"
LIC_CACHE = ROOT / "regulatory/SOFTWARE/soup-licences.json"
EXTRA = ROOT / "regulatory/SOFTWARE/soup-extra.csv"

LOCKS = [
    ("host-workspace", "firmware-rs/Cargo.lock"),
    ("bench-app", "firmware-rs/openpatch-bench/Cargo.lock"),
    ("bootloader", "firmware-rs/openpatch-bootloader/Cargo.lock"),
]
SWIFT = "ios/OpenPatchKit/OpenPatchCore/Package.resolved"

# Purpose of crates we know (direct dependencies and well known ones); everything else is labelled transitive.
PURPOSE = {
    "heapless": "fixed-capacity collections without allocation (core data structures)",
    "aes": "AES block cipher (frame protection, AES-CCM)",
    "ccm": "AES-CCM AEAD mode (frame protection)",
    "x25519-dalek": "X25519 key agreement (pairing / session handshake)",
    "curve25519-dalek": "elliptic-curve arithmetic for X25519",
    "hkdf": "HKDF-SHA256 key derivation (session keys)",
    "hmac": "HMAC-SHA256 (key confirmation)",
    "sha2": "SHA-256 (transcript hash)",
    "subtle": "constant-time comparison (key confirmation)",
    "rand_core": "RNG trait (ChaCha20 DRBG seeded from the hardware TRNG)",
    "chacha20": "ChaCha20 DRBG for ephemeral secrets",
    "embassy-executor": "async executor, interrupt executors (safety task priority)",
    "embassy-time": "timekeeping and tickers",
    "embassy-nrf": "nRF52840 peripheral drivers (PWM, SAADC, TWIM, GPIOTE, QDEC)",
    "embassy-sync": "channels / mutexes between tasks",
    "trouble-host": "BLE host stack (GATT, pairing)",
    "nrf-sdc": "Nordic SoftDevice Controller bindings (BLE link layer, binary blob)",
    "nrf-mpsl": "Nordic multiprotocol service layer (radio scheduling, flash timeslots; binary blob)",
    "sequential-storage": "wear-levelled key/value storage in flash",
    "embedded-storage": "flash trait",
    "embedded-hal": "hardware abstraction traits",
    "defmt": "logging for embedded targets (not in the safety path)",
    "cortex-m": "Cortex-M core access (critical sections, intrinsics)",
    "cortex-m-rt": "Cortex-M start-up / vector table",
    "panic-probe": "panic handler for the bench build",
    "embassy-boot": "bootloader library (swap, MCUboot-compatible state)",
    "proptest": "property-based testing (host test only)",
    "cc": "C compiler driver for the differential tests (host test only)",
    "serde": "serialisation for test vectors (host test only)",
    "serde_json": "JSON for test vectors (host test only)",
    "swift-crypto": "cryptography on non-Apple platforms (iOS uses CryptoKit); X25519/HKDF/HMAC/SHA-256",
    "swift-asn1": "ASN.1 parsing, transitive dependency of swift-crypto",
}

TEST_ONLY_ROOTS = {"differential-tests"}


def parse_lock(path: Path):
    t = path.read_text(encoding="utf-8")
    pkgs = []
    for block in t.split("[[package]]")[1:]:
        name = re.search(r'^name = "(.+?)"', block, re.M).group(1)
        ver = re.search(r'^version = "(.+?)"', block, re.M).group(1)
        src = re.search(r'^source = "(.+?)"', block, re.M)
        deps = []
        m = re.search(r"^dependencies = \[(.*?)^\]", block, re.M | re.S)
        if m:
            deps = [re.sub(r"\s.*", "", d.strip().strip(",").strip('"')) for d in m.group(1).splitlines() if d.strip()]
            deps = [d.strip('"') for d in deps]
        pkgs.append({"name": name, "version": ver, "source": src.group(1) if src else None, "deps": deps})
    return pkgs


def reach(pkgs):
    """Map package name -> set of local roots (workspace members, no source) that reach it."""
    by_name = defaultdict(list)
    for p in pkgs:
        by_name[p["name"]].append(p)
    local = {p["name"] for p in pkgs if p["source"] is None}
    roots = [p for p in pkgs if p["source"] is None]
    res = defaultdict(set)
    for r in roots:
        seen = set()
        stack = [r["name"]]
        while stack:
            n = stack.pop()
            if n in seen:
                continue
            seen.add(n)
            res[n].add(r["name"])
            nd = None
            # the lock file merges dev-dependencies; first-party crates are followed through their
            # Cargo.toml normal dependencies so test-only crates stay out of the shipped set
            if n in local and not (r["name"] in TEST_ONLY_ROOTS and n == r["name"]):
                nd = local_manifest_deps(n)
            if nd is None:
                nd = [d for p in by_name.get(n, []) for d in p["deps"]]
            stack.extend(nd)
    return roots, res


def local_manifest_deps(name: str):
    """Normal (non-dev, non-build) dependencies of a first-party crate, from its Cargo.toml."""
    import tomllib
    base = ROOT / "firmware-rs"
    for tp in list(base.glob(f"{name}/Cargo.toml")) + list(base.glob(f"*/{name}/Cargo.toml")):
        d = tomllib.loads(tp.read_text(encoding="utf-8"))
        deps = dict(d.get("dependencies") or {})
        for tgt in (d.get("target") or {}).values():
            deps.update(tgt.get("dependencies") or {})
        out = list(deps)
        out += [v["package"] for v in deps.values() if isinstance(v, dict) and "package" in v]
        return out
    return None


def classify(used_by: set, roots: set, scope: str) -> str:
    prod = used_by - TEST_ONLY_ROOTS
    if not prod:
        return "test-only (not shipped)"
    if scope == "bootloader":
        return "bootloader (shipped, update path)"
    if used_by & {"openpatch-core", "openpatch-proto"}:
        return "shipped, safety/security path (core or protocol)"
    return "shipped (bench app, outside the dosing core)"


def build():
    rows = []
    first_party = []
    for scope, rel in LOCKS:
        p = ROOT / rel
        if not p.exists():
            continue
        pkgs = parse_lock(p)
        roots, res = reach(pkgs)
        root_names = {r["name"] for r in roots}
        direct = set()
        for r in roots:
            direct.update(r["deps"])
        for r in roots:
            first_party.append({"scope": scope, "name": r["name"], "version": r["version"]})
        for pk in pkgs:
            if pk["source"] is None:
                continue
            ub = res.get(pk["name"], set())
            rows.append({
                "ecosystem": "cargo", "scope": scope, "name": pk["name"], "version": pk["version"],
                "direct": pk["name"] in direct,
                "used_by": sorted(ub),
                "classification": classify(ub, root_names, scope),
                "purpose": PURPOSE.get(pk["name"], "transitive dependency (purpose: see parent crate)" if pk["name"] not in direct else "direct dependency (purpose to be written)"),
                "source": pk["source"].split("+")[0],
            })
    sp = ROOT / SWIFT
    if sp.exists():
        d = json.loads(sp.read_text())
        for pin in d.get("pins", []):
            nm = pin["identity"]
            rows.append({
                "ecosystem": "swiftpm", "scope": "ios-core", "name": nm, "version": pin["state"].get("version", pin["state"].get("revision", "?")),
                "direct": nm == "swift-crypto", "used_by": ["OpenPatchCore"],
                "classification": "shipped, safety/security path (core or protocol)" if nm == "swift-crypto" else "shipped (transitive)",
                "purpose": PURPOSE.get(nm, "direct dependency (purpose to be written)"),
                "source": pin.get("location", ""),
            })
    # merge same (ecosystem, name, version) over scopes
    merged: dict[tuple, dict] = {}
    for r in rows:
        k = (r["ecosystem"], r["name"], r["version"])
        if k in merged:
            m = merged[k]
            m["scope"] = ",".join(sorted(set(m["scope"].split(",")) | {r["scope"]}))
            m["used_by"] = sorted(set(m["used_by"]) | set(r["used_by"]))
            m["direct"] = m["direct"] or r["direct"]
            order = ["shipped, safety/security path (core or protocol)", "bootloader (shipped, update path)",
                     "shipped (bench app, outside the dosing core)", "shipped (transitive)", "test-only (not shipped)"]
            m["classification"] = min(m["classification"], r["classification"], key=lambda x: order.index(x) if x in order else 99)
        else:
            merged[k] = dict(r)
    out = sorted(merged.values(), key=lambda r: (r["ecosystem"], r["classification"], r["name"], r["version"]))
    # extras
    extra = []
    if EXTRA.exists():
        extra = list(csv.DictReader(EXTRA.read_text(encoding="utf-8").splitlines()))
    return out, extra, first_party


def load_lic():
    if LIC_CACHE.exists():
        return json.loads(LIC_CACHE.read_text())
    return {}


def fetch_licences(rows):
    cache = load_lic()
    todo = [r for r in rows if r["ecosystem"] == "cargo" and f"{r['name']}@{r['version']}" not in cache]
    print(f"{len(todo)} licences to fetch (1 request/s)")
    for i, r in enumerate(todo, 1):
        key = f"{r['name']}@{r['version']}"
        url = f"https://crates.io/api/v1/crates/{r['name']}/{r['version']}"
        req = urllib.request.Request(url, headers={"User-Agent": "openpatch-soup-tool (generic client)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                v = json.load(resp)["version"]
                cache[key] = v.get("license") or "UNKNOWN"
        except Exception as e:  # network errors are not fatal; leave the entry open
            print("  fail", key, e)
            continue
        if i % 25 == 0:
            LIC_CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True))
            print(f"  {i}/{len(todo)}")
        time.sleep(1.0)
    LIC_CACHE.write_text(json.dumps(cache, indent=0, sort_keys=True))


SWIFT_LIC = {"swift-crypto": "Apache-2.0", "swift-asn1": "Apache-2.0"}


def lic_for(r, cache):
    if r["ecosystem"] == "swiftpm":
        return SWIFT_LIC.get(r["name"], "UNKNOWN (verify)")
    return cache.get(f"{r['name']}@{r['version']}", "UNKNOWN (run --fetch-licences)")


def render(rows, extra, first_party, cache):
    unk = [r for r in rows if lic_for(r, cache).startswith("UNKNOWN")]
    o = ["# SOUP list (IEC 62304 5.3.3, 7.1.3, 8.1.2) - generated\n",
         "> GENERATED by `python3 regulatory/tools/soup.py`. Do not edit by hand; edit `soup-extra.csv` or the tool.",
         "> Test project, not a medical device. The list is the regulatory SOUP inventory; the CycloneDX SBOM is produced by `security/` (planned).\n",
         "## How to read this\n",
         "- **Class C** items (the dosing core and the protocol) are the first-party crates `openpatch-core` and `openpatch-proto`. Dependencies reached from them are marked *safety/security path*; these need a SOUP anomaly review before any release (IEC 62304 8.1.2) and a functional/performance requirement statement (5.3.3).",
         "- **Known anomalies** column is a placeholder: no review has been done. A legal manufacturer must check the published anomaly lists (RustSec advisory DB, GitHub advisories, vendor errata) per version at each release and record the outcome here.",
         "- Licences come from the crates.io API (cached in `soup-licences.json`); SPDX expressions as published, not independently verified. Copyleft or unknown entries need a licence review (the project itself is PolyForm-Noncommercial / CC BY-NC-SA, see `LICENSE.md`).",
         "- Test-only crates are listed for completeness; they are not shipped in the product and are outside IEC 62304 SOUP scope.\n"]
    cargo = [r for r in rows if r["ecosystem"] == "cargo"]
    swift = [r for r in rows if r["ecosystem"] == "swiftpm"]
    o.append(f"## Summary\n\n| Item | Count |\n|---|---|\n| Rust packages (distinct name+version) | {len(cargo)} |\n| of which shipped, safety/security path | {sum(1 for r in cargo if r['classification'].startswith('shipped, safety'))} |\n| of which shipped, other | {sum(1 for r in cargo if r['classification'].startswith(('shipped (', 'bootloader')))} |\n| of which test-only | {sum(1 for r in cargo if r['classification'].startswith('test-only'))} |\n| Swift packages | {len(swift)} |\n| Extra SOUP (blobs, OS, host apps) | {len(extra)} |\n| Licence unknown / not yet fetched | {len(unk)} |\n| First-party packages (not SOUP) | {len(first_party)} |\n")
    o.append("## Extra SOUP not in a lock file\n")
    o.append("| Name | Version / source | Licence | Purpose | Safety relevance | Known anomalies |\n|---|---|---|---|---|---|")
    for e in extra:
        o.append(f"| {e['name']} | {e['version']} | {e['licence']} | {e['purpose']} | {e['relevance']} | not yet assessed (placeholder) |")
    for eco, title, lst in (("cargo", "Rust crates", cargo), ("swiftpm", "Swift packages", swift)):
        o.append(f"\n## {title}\n")
        o.append("| Name | Version | Licence | Direct | Scope | Classification | Purpose | Known anomalies |\n|---|---|---|---|---|---|---|---|")
        for r in lst:
            o.append(f"| {r['name']} | {r['version']} | {lic_for(r, cache)} | {'yes' if r['direct'] else 'no'} | {r['scope']} | {r['classification']} | {r['purpose']} | not yet assessed (placeholder) |")
    o.append("\n## First-party packages (for reference, not SOUP)\n")
    o.append("| Scope | Package | Version |\n|---|---|---|")
    for f in first_party:
        o.append(f"| {f['scope']} | {f['name']} | {f['version']} |")
    o.append("")
    return "\n".join(o)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--fetch-licences", action="store_true")
    ap.add_argument("--check", action="store_true", help="fail if soup.json is stale versus the lock files")
    a = ap.parse_args(argv)
    rows, extra, fp = build()
    if a.fetch_licences:
        fetch_licences(rows)
    cache = load_lic()
    for r in rows:
        r["licence"] = lic_for(r, cache)
    doc = {"packages": rows, "extra": extra, "first_party": fp}
    if a.check:
        if not OUT_JSON.exists():
            print("soup.json missing")
            return 1
        old = json.loads(OUT_JSON.read_text())
        key = lambda d: sorted((p["ecosystem"], p["name"], p["version"]) for p in d["packages"])
        if key(old) != key(doc):
            print("STALE: lock files changed; run python3 regulatory/tools/soup.py and commit SOUP.md / soup.json")
            return 1
        print(f"soup.json up to date ({len(rows)} packages)")
        return 0
    OUT_JSON.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    OUT_MD.write_text(render(rows, extra, fp, cache), encoding="utf-8")
    unk = sum(1 for r in rows if r["licence"].startswith("UNKNOWN"))
    print(f"{len(rows)} packages ({sum(1 for r in rows if r['ecosystem']=='cargo')} cargo, "
          f"{sum(1 for r in rows if r['ecosystem']=='swiftpm')} swift), {len(extra)} extra, {unk} licences unknown")
    print("wrote", OUT_MD.relative_to(ROOT), "and", OUT_JSON.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
