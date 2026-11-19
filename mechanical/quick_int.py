import re
import sys
from pathlib import Path

sys.path.insert(0, ".")
import check
import v010_gen

size = sys.argv[1] if len(sys.argv) > 1 else "OP-100"
sc = Path(f"out/v010/{size}.sc")
res = check.eval_design(sc, v010_gen.EXCLUDE_PAIRS)
m = next(r for r in res if "bodies" in r and "body_count" in r)
i = next(r for r in res if "interferences" in r)
print(m["body_count"], "bodies")
lo, hi = check.envelope(m["bodies"])
print("env", [round(hi[k] - lo[k], 3) for k in range(3)], lo, hi)
for x in i["interferences"]:
    if x.get("volume_mm3", 1) > 1e-4:
        print("INT", x["a"], x["b"], round(x["volume_mm3"], 4))
for u in i.get("unchecked", []):
    print("UNCHK", u)
print("open:", [b["name"] for b in m["bodies"] if not b.get("closed")])
print("frag:", [b["name"] for b in m["bodies"] if re.search(r" \(\d+\)$", b["name"])])
