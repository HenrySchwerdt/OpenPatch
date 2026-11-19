#!/usr/bin/env bash
# Regenerate all model variants and re-run every proof. TEST PROJECT, not a medical device.
#
# Tools (pinned, see security/formal/README.md for how to install):
#   tamarin-prover 1.10.0 (+ maude 3.2), proverif 2.05, python3
# Usage: security/formal/run.sh [outdir]      (default: security/formal/results)
# Exit code 0 only if every result equals the EXPECTED value below (so CI fails when a model or the protocol drifts).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$HERE/results}"
GEN="$(mktemp -d)"
mkdir -p "$OUT"
export LC_ALL=C.UTF-8
fail=0

pp() { python3 -I "$HERE/preprocess.py" "$@"; }
expect() { # expect <name> <got> <want>
  if [ "$2" = "$3" ]; then printf '  ok   %-58s %s\n' "$1" "$2"; else printf '  FAIL %-58s got %s, want %s\n' "$1" "$2" "$3"; fail=1; fi
}

echo "== tools"
{ tamarin-prover --version 2>&1 | grep -m1 "tamarin-prover 1" ; proverif -help 2>&1 | head -1; } | tee "$OUT/tools.txt"
sha256sum "$HERE"/tamarin/*.in "$HERE"/proverif/*.in | sed "s#$HERE/##" >> "$OUT/tools.txt"

# ---------------------------------------------------------------- Tamarin
tam() { # tam <template> <outname> [-DFLAG]
  local t="$1" n="$2"; shift 2
  pp "$HERE/tamarin/$t" "$GEN/$n.spthy" "$@"
  cp "$GEN/$n.spthy" "$OUT/$n.spthy"
  ( ulimit -v 8000000 2>/dev/null; timeout 1500 tamarin-prover --prove "$GEN/$n.spthy" > "$OUT/$n.tamarin.txt" 2>&1 )
  grep -E "^  [a-z_]+ \(" "$OUT/$n.tamarin.txt" | sed 's/ (\([0-9]* steps\))//' | sed 's/[0-9]* steps//' || true
}
res() { # res <file> <lemma>  -> verified|falsified|other
  local l; l=$(grep -E "^  $2 \(" "$OUT/$1.tamarin.txt" | head -1)
  case "$l" in *verified*) echo verified;; *falsified*) echo falsified;; *) echo "other:$l";; esac
}

echo "== Tamarin: pairing, TOFU (current bench default)"
tam openpatch_pairing.spthy.in pairing_tofu >/dev/null
expect "TOFU  executable_pairing"                   "$(res pairing_tofu executable_pairing)" verified
expect "TOFU  pairing_secret_ps (attack expected)"  "$(res pairing_tofu pairing_secret_ps)" falsified
expect "TOFU  pairing_agreement_app (attack exp.)"  "$(res pairing_tofu pairing_agreement_app)" falsified
expect "TOFU  pairing_agreement_pod_injective"      "$(res pairing_tofu pairing_agreement_pod_injective)" falsified

echo "== Tamarin: pairing, high-entropy OOB"
tam openpatch_pairing.spthy.in pairing_oob -DOOB >/dev/null
expect "OOB   executable_pairing"                   "$(res pairing_oob executable_pairing)" verified
expect "OOB   pairing_secret_ps"                    "$(res pairing_oob pairing_secret_ps)" verified
expect "OOB   pairing_agreement_app"                "$(res pairing_oob pairing_agreement_app)" verified
expect "OOB   pairing_agreement_pod_injective"      "$(res pairing_oob pairing_agreement_pod_injective)" verified

echo "== Tamarin: session handshake"
tam openpatch_session.spthy.in session >/dev/null
for l in executable_session session_key_secrecy_ps_only session_forward_secrecy session_agreement_pod_injective session_agreement_app; do
  expect "SESS  $l" "$(res session $l)" verified
done

# ---------------------------------------------------------------- ProVerif
pv() { # pv <template> <outname> [-DFLAG]
  local t="$1" n="$2"; shift 2
  pp "$HERE/proverif/$t" "$GEN/$n.pv" "$@"
  cp "$GEN/$n.pv" "$OUT/$n.pv"
  timeout 600 proverif "$GEN/$n.pv" > "$OUT/$n.proverif.txt" 2>&1
}
pvres() { grep -E "^RESULT" "$OUT/$1.proverif.txt" | sed -n "${2}p" | sed -E 's/.* is (true|false)\.$/\1/; s/^RESULT \(.*$/x/'; }
nth() { grep -E "^RESULT" "$OUT/$1.proverif.txt" | grep -vE "^RESULT \((even|but) " | sed -n "${2}p" | sed -E 's/.* is (true|false)\.?.*$/\1/'; }

echo "== ProVerif: pairing (cross-check + guessing)"
pv openpatch_pairing.pv.in pv_pairing_tofu -DTOFU
expect "PV TOFU  PS secrecy (attack expected)"       "$(nth pv_pairing_tofu 1)" false
expect "PV TOFU  agreement (attack expected)"        "$(nth pv_pairing_tofu 2)" false
pv openpatch_pairing.pv.in pv_pairing_oob -DOOB
expect "PV OOB   attacker learns oob"                "$(nth pv_pairing_oob 1)" true
expect "PV OOB   PS secrecy"                         "$(nth pv_pairing_oob 2)" true
expect "PV OOB   injective agreement pod->app"       "$(nth pv_pairing_oob 3)" true
expect "PV OOB   agreement app->pod"                 "$(nth pv_pairing_oob 4)" true
pv openpatch_pairing.pv.in pv_pairing_weak -DWEAK
expect "PV WEAK  weak secret (offline guess, FINDING-002)" "$(nth pv_pairing_weak 1)" false
pv openpatch_pairing.pv.in pv_pairing_cpace -DCPACE
expect "PV CPACE weak secret (no offline guess)"     "$(nth pv_pairing_cpace 1)" true
expect "PV CPACE PS secrecy"                         "$(nth pv_pairing_cpace 2)" true
expect "PV CPACE injective agreement"                "$(nth pv_pairing_cpace 3)" true

echo "== ProVerif: session + data channel"
pv openpatch_session.pv.in pv_session_spec
expect "PV SESS  AppSecret forward secrecy (phase 1 PS leak)" "$(nth pv_session_spec 1)" true
expect "PV SESS  PodSecret forward secrecy"           "$(nth pv_session_spec 2)" true
expect "PV SESS  inj. agreement pod->app"             "$(nth pv_session_spec 3)" true
expect "PV SESS  inj. agreement app->pod"             "$(nth pv_session_spec 4)" true
expect "PV SESS  command authenticity"                "$(nth pv_session_spec 5)" true
expect "PV SESS  response authenticity"               "$(nth pv_session_spec 6)" true
expect "PV SESS  no reflected acceptance (spec)"      "$(nth pv_session_spec 7)" true
pv openpatch_session.pv.in pv_session_reflect -DREFLECT
expect "PV SESS  reflection reachable (current code, FINDING-001)" "$(nth pv_session_reflect 7)" false
pv openpatch_session.pv.in pv_session_leak0 -DLEAK0
expect "PV SESS  sanity: PS known from start -> secrecy fails" "$(nth pv_session_leak0 1)" false
expect "PV SESS  sanity: PS known from start -> agreement fails" "$(nth pv_session_leak0 3)" false

echo
if [ "$fail" = 0 ]; then echo "ALL EXPECTED RESULTS REPRODUCED"; else echo "MISMATCH (see above)"; fi
rm -rf "$GEN"
exit "$fail"
