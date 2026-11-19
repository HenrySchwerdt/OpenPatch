"""Quick path sweep of assembly_sequence_v010.json without the alternative search: python3 quick_paths.py [OP-100] [step]"""
import sys
from pathlib import Path

sys.path.insert(0, ".")
import check_assembly as CA

size = sys.argv[1] if len(sys.argv) > 1 else "OP-100"
step = float(sys.argv[2]) if len(sys.argv) > 2 else 0.25
out = Path("out/v010")
rules, seq = CA.jload(CA.RULES_FILE), CA.jload(CA.seq_path(out))
M = CA.Model(out, size)
S = CA.Sequencer(M, seq, rules, step)
for st in seq["steps"]:
    r = S.run_step(st, alt_search=False)
    line = f"{r['id']:4} {r['status']:18} {r['title'][:60]}"
    print(line)
    if r["status"] in ("BLOCKED", "FINAL-INTERFERENCE"):
        for b in r.get("blocked_by", [])[:4]:
            print(f"      by {b['body']}: first at s={b['first_s']:.2f} max {b['max_mm3']:.3f} mm3 bbox {b['bbox']}")
