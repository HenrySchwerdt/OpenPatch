#!/usr/bin/env bash
# Fail if any workflow step uses a GitHub Action that is not pinned to a full 40-hex commit SHA (tags are mutable: the
# tj-actions/changed-files compromise of March 2025 rewrote tags). Also flags `pull_request_target`, `write-all` and
# workflow-level write permissions. TEST PROJECT, not a medical device.
set -u
cd "$(dirname "$0")/../.."
fail=0
for f in .github/workflows/*.yml .github/workflows/*.yaml; do
  [ -f "$f" ] || continue
  while IFS= read -r line; do
    ref=$(echo "$line" | sed -E 's/^[^:]*uses:[[:space:]]*//; s/[[:space:]]*#.*$//')
    case "$ref" in ./*|docker://*) continue;; esac
    if ! echo "$ref" | grep -Eq '@[0-9a-f]{40}$'; then echo "UNPINNED  $f: $ref"; fail=1; fi
  done < <(grep -E '^[[:space:]-]*uses:' "$f")
  if grep -nE 'pull_request_target|permissions:[[:space:]]*write-all' "$f" > /tmp/risky.$$; then
    sed "s#^#RISKY     $f:#" /tmp/risky.$$; fail=1
  fi
  rm -f /tmp/risky.$$
done
[ "$fail" = 0 ] && echo "all actions pinned" || echo "pin them with security/supply-chain/pin-actions.sh (or git ls-remote <action> refs/tags/<tag>^{})"
exit $fail
