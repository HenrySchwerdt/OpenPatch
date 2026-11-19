#!/usr/bin/env bash
# Rewrite `uses: owner/repo@tag` to `uses: owner/repo@<40-hex sha> # tag` in all workflows (run on a maintainer machine with
# `gh auth login`; the sandbox that wrote these files had no API access, so NO SHA was invented there). TEST PROJECT.
set -euo pipefail
cd "$(dirname "$0")/../.."
for f in .github/workflows/*.yml; do
  grep -oE 'uses:[[:space:]]*[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@v[0-9][A-Za-z0-9._-]*' "$f" | sed -E 's/uses:[[:space:]]*//' | sort -u | while read -r ref; do
    repo="${ref%@*}"; tag="${ref#*@}"
    sha=$(gh api "repos/${repo%%/[^/]*/*}/git/ref/tags/$tag" --jq '.object.sha' 2>/dev/null || gh api "repos/$repo/git/ref/tags/$tag" --jq '.object.sha')
    typ=$(gh api "repos/$repo/git/ref/tags/$tag" --jq '.object.type')
    [ "$typ" = tag ] && sha=$(gh api "repos/$repo/git/tags/$sha" --jq '.object.sha')
    echo "$repo $tag -> $sha"
    sed -i -E "s#(uses:[[:space:]]*)${ref}\$#\1${repo}@${sha} \# ${tag}#" "$f"
  done
done
security/supply-chain/check-action-pins.sh
