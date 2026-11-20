#!/usr/bin/env python3
"""Language check: the repository is English only (docs, code comments, strings, scripts, generated reports).

Fails (exit code 1) when a tracked text file contains German text that is not covered by the allowlist.
The one intended exception is the iOS German localisation (de.lproj), which is allowlisted.

Detection (heuristic, per line, after removing URLs and allowlisted patterns):
  1. any umlaut or sharp s (ae/oe/ue with dots, and the sharp s) -> violation;
  2. transliterated German (ae, oe, ue, ss spellings): the line contains at least TWO distinct common German
     function words (und, nicht, oder, ...) or at least ONE distinctive German technical word
     (Gehaeuse, Platine, Bauteil, ...).

Allowlist: tools/language-allowlist.txt (see the header of that file for the format).

Usage:
  python3 tools/check_language.py                   # check all git-tracked files of the repository
  python3 tools/check_language.py --root DIR        # check another checkout
  python3 tools/check_language.py --self-test       # check the detector itself
  python3 tools/check_language.py --list-allowlisted-paths

Standard library only.
"""
import argparse
import os
import re
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_ALLOWLIST = os.path.join(REPO, "tools", "language-allowlist.txt")

# Words that are (almost) never English and rarely appear in code identifiers. Two distinct hits on one line flag it.
GERMAN_FUNCTION_WORDS = (
    "und oder nicht nur ohne fuer ueber werden wird wurde wurden sind ist auch noch kein keine keinen keiner dass wenn weil "
    "zum zur zwischen sowie damit eine einen einer eines dieser diese dieses diesen mit bei nach vom von auf aus "
    "als wie hier dort sich kann muss soll darf hat haben aber doch sehr mehr jede jeder jedes alle allen beim"
).split()
# Weak words are common in English text or code as well ("as", "all" is not in the list, "mit" appears in identifiers):
# they only count together with a non-weak word.
WEAK = set("mit bei nach vom von auf aus als wie hier dort sich kann muss soll darf hat haben aber doch sehr mehr nur alle ist".split())

# Distinctive German technical vocabulary (transliterated or not). One hit flags the line.
GERMAN_DISTINCT = (
    r"Bauteile?|Bestueck\w*|Bestück\w*|Gehaeuse\w*|Gehäuse\w*|Platine\w*|Leiterplatte\w*|Spule\w*|Akku\w*|Kanuel\w*|Kanül\w*|"
    r"Hoehe\w*|Höhe\w*|Laenge\w*|Länge\w*|Breite\w*|Loetpad\w*|Lötpad\w*|Loetstelle\w*|Lötstelle\w*|Schaetz\w*|Schätz\w*|geschaetzt|"
    r"Pruef\w*|Prüf\w*|pruefen|prüfen|Hersteller\w*|Gedaechtnis|Gedächtnis|Rueck\w*|Rück\w*|Stueck\w*|Stück\w*|Schraube\w*|Schrauben\w*|"
    r"Zahnrad\w*|Zahnraeder|Getriebe\w*|Schlitten|Kolben\w*|Dichtung\w*|Spindel\w*|Taster\w*|Deckel|Widerstand|Abstand\w*|"
    r"Antrieb\w*|Ergebnis\w*|Beschreibung|Aenderung\w*|Änderung\w*|Hinweis\w*|Achtung|Entscheidung\w*|Kosten\w*|Preis\w*|"
    r"Aussparung\w*|Fuehrung\w*|Führung\w*|Stirnwand|Bohrung\w*|Gewinde\w*|Mutter\b|Feder\b|Federn|Kabel\w*|Nadelhuelse|Nadelhülse|"
    r"Zeichnung\w*|Entwurf|Erlaeuter\w*|Erläuter\w*|Voraussetzung\w*|Beispiel\w*|Anleitung|Zusammenbau|Montage|Klebstoff|Kleber\b|"
    r"Klasse\w*|Lager\b|Zeile\w*|Wert\w*|Seite\b|Kante\w*|Ecke\w*|Mitte\b|Oberseite|Unterseite|Tabelle\w*|Datenblatt\w*|"
    r"Stromversorgung\w*|Ladestrom|Spannung\w*|Nadel\w*|Nutzer|Gewicht|Menge\b|Mengen|Lieferzeit|Bestellung\w*|Versand|"
    r"Haut|Klett\w*|Ruecken|Rücken|Vorspannung|Pratze\w*|Boeck\w*|Böck\w*|Saettel|Sättel|Regal\b|Rippe\w*|Pilotloch\w*"
)
# Only words that do not occur in English prose or in code identifiers are listed.
DISTINCT_RE = re.compile(r"(?<![A-Za-z0-9_])(?:%s)(?![A-Za-z0-9_])" % GERMAN_DISTINCT)
FUNC_RE = re.compile(r"(?<![A-Za-z0-9_])(%s)(?![A-Za-z0-9_])" % "|".join(sorted(set(GERMAN_FUNCTION_WORDS))), re.I)
UMLAUT_RE = re.compile("[äöüÄÖÜß]")
URL_RE = re.compile(r"(?:https?|ftp)://\S+|www\.\S+|<[^<>\s]+\.[a-z]{2,}[^<>\s]*>", re.I)

# Binary or generated formats that are never checked.
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".tgz", ".xz", ".7z", ".bz2", ".jar", ".wasm",
    ".step", ".stp", ".stl", ".3mf", ".dxf", ".dwg", ".gbr", ".drl", ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp4", ".mov",
    ".bin", ".hex", ".elf", ".a", ".o", ".so", ".dylib", ".exe", ".class", ".pyc", ".sqlite", ".db", ".glb", ".gltf",
}
MAX_BYTES = 4 * 1024 * 1024


def load_allowlist(path):
    """Returns (path_globs, ignore_global, ignore_scoped). Format: see tools/language-allowlist.txt."""
    path_globs, ignore_global, ignore_scoped = [], [], []
    if not os.path.exists(path):
        return path_globs, ignore_global, ignore_scoped
    with open(path, encoding="utf-8") as f:
        for n, raw in enumerate(f, 1):
            line = raw.split("  #", 1)[0].rstrip("\n").strip()
            if not line or line.startswith("#"):
                continue
            key, _, val = line.partition(":")
            key, val = key.strip(), val.strip()
            try:
                if key == "path":
                    path_globs.append(val)
                elif key == "ignore":
                    ignore_global.append(re.compile(val))
                elif key == "ignore-in":
                    g, _, rx = val.partition("::")
                    ignore_scoped.append((g.strip(), re.compile(rx.strip())))
                else:
                    raise ValueError("unknown key %r" % key)
            except (ValueError, re.error) as e:
                sys.exit("%s:%d: invalid allowlist entry: %s" % (path, n, e))
    return path_globs, ignore_global, ignore_scoped


def glob_match(rel, pattern):
    """Glob match where '**' matches across directories and a trailing '/**' matches the directory contents."""
    rx = ""
    i = 0
    while i < len(pattern):
        if pattern.startswith("**/", i):
            rx += "(?:.*/)?"
            i += 3
        elif pattern.startswith("/**", i) and i + 3 == len(pattern):
            rx += "(?:/.*)?"
            i += 3
        elif pattern.startswith("**", i):
            rx += ".*"
            i += 2
        elif pattern[i] == "*":
            rx += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            rx += "[^/]"
            i += 1
        else:
            rx += re.escape(pattern[i])
            i += 1
    return re.fullmatch(rx, rel) is not None


def tracked_files(root):
    try:
        out = subprocess.run(["git", "-C", root, "ls-files", "-z"], check=True, capture_output=True).stdout
        return [p for p in out.decode("utf-8", "surrogateescape").split("\0") if p]
    except (OSError, subprocess.CalledProcessError):
        files = []
        for d, dirs, names in os.walk(root):
            dirs[:] = [x for x in dirs if x not in (".git", "node_modules", "target", "__pycache__")]
            files += [os.path.relpath(os.path.join(d, n), root) for n in names]
        return sorted(files)


def line_findings(text):
    """Returns a short reason string if the (already cleaned) line looks German, else None."""
    m = UMLAUT_RE.search(text)
    if m:
        return "umlaut/sharp s %r" % m.group(0)
    m = DISTINCT_RE.search(text)
    if m:
        return "German word %r" % m.group(0)
    words = {w.lower() for w in FUNC_RE.findall(text)}
    strong = words - WEAK
    if len(words) >= 2 and strong or len(strong) >= 2:
        return "German words %s" % sorted(words)
    return None


def check_file(root, rel, ignore_global, ignore_scoped):
    full = os.path.join(root, rel)
    if os.path.splitext(rel)[1].lower() in BINARY_EXT or not os.path.isfile(full):
        return []
    try:
        if os.path.getsize(full) > MAX_BYTES:
            return []
        data = open(full, "rb").read()
    except OSError:
        return []
    if b"\0" in data[:8192]:
        return []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1")
    scoped = [rx for g, rx in ignore_scoped if glob_match(rel, g)]
    found = []
    for n, line in enumerate(text.splitlines(), 1):
        clean = URL_RE.sub(" ", line)
        for rx in ignore_global:
            clean = rx.sub(" ", clean)
        for rx in scoped:
            clean = rx.sub(" ", clean)
        reason = line_findings(clean)
        if reason:
            found.append((n, reason, line.strip()[:160]))
    return found


def run(root, allowlist):
    path_globs, ignore_global, ignore_scoped = load_allowlist(allowlist)
    bad = 0
    nfiles = 0
    for rel in tracked_files(root):
        rel = rel.replace(os.sep, "/")
        if any(glob_match(rel, g) for g in path_globs):
            continue
        nfiles += 1
        for n, reason, text in check_file(root, rel, ignore_global, ignore_scoped):
            print("%s:%d: %s: %s" % (rel, n, reason, text))
            bad += 1
    if bad:
        print("\nFAIL: %d line(s) with German text in %d checked files. Translate them to English, or (only for proper nouns, "
              "verbatim quotes or the iOS German localisation) add an entry to %s." %
              (bad, nfiles, os.path.relpath(allowlist, root) if allowlist.startswith(root) else allowlist))
        return 1
    print("OK: no German text outside the allowlist (%d files checked, %d allowlisted path patterns)." % (nfiles, len(path_globs)))
    return 0


def self_test():
    must_flag = [
        "# Gehaeuse: Boden und Deckel",
        "x = 1  # Wert nicht verfuegbar, oder doch",
        "Die Platine ist 17 mm lang",
        "Kein MCU-Ausgang direkt auf MOT_ALLOW",
        "Maße in mm",
        "Qi-Spule Ø17.6 mm",
        "ueber dem Akku",
    ]
    must_pass = [
        "# Housing: floor, lid and gasket",
        "The motor can only move if both paths enable it.",
        "SPDX-License-Identifier: MIT",
        "let (mut lat, mut und) = (Vec::new(), Vec::new());",
        "see https://www.berrybase.de/it/soldered-li-ion-akku-lithium-polymer-350824-3-7v-40mah-mit-2-pin-jst-stecker",
        "Ø6 mm stepper, 3 V, 20 steps/rev",
    ]
    ok = True
    for s in must_flag:
        if not line_findings(URL_RE.sub(" ", s)):
            print("self-test: expected a finding for %r" % s)
            ok = False
    for s in must_pass:
        r = line_findings(URL_RE.sub(" ", s))
        if r:
            print("self-test: unexpected finding %r for %r" % (r, s))
            ok = False
    print("self-test OK" if ok else "self-test FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=REPO, help="repository root (default: this repository)")
    ap.add_argument("--allowlist", default=DEFAULT_ALLOWLIST)
    ap.add_argument("--self-test", action="store_true")
    ap.add_argument("--list-allowlisted-paths", action="store_true")
    a = ap.parse_args()
    if a.self_test:
        return self_test()
    if a.list_allowlisted_paths:
        print("\n".join(load_allowlist(a.allowlist)[0]))
        return 0
    return run(os.path.abspath(a.root), os.path.abspath(a.allowlist))


if __name__ == "__main__":
    sys.exit(main())
