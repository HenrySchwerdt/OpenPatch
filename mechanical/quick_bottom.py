"""Build only the bottom shell (fast loop for housing features): python3 quick_bottom.py [OP-100]"""
import json
import subprocess
import sys

sys.path.insert(0, ".")
import op_pod
import op_pod_shell
from op_cmds import Script
from op_layout import find_cli

size = sys.argv[1] if len(sys.argv) > 1 else "OP-100"
p = op_pod.prepare(json.load(open("params.json")))
L = op_pod.layout(p, size)
L["geo"] = op_pod.geometry(p, L)
s = Script()
op_pod_shell.build_bottom(s, p, L)
open("/tmp/claude-0/-home-user-ai-insulin-pump/81d3c0e6-4bc1-5e65-bb19-a2d3a00bcb66/scratchpad/qb.json", "w").write(json.dumps(s.dumps()))
r = subprocess.run([find_cli(), "run", "/tmp/claude-0/-home-user-ai-insulin-pump/81d3c0e6-4bc1-5e65-bb19-a2d3a00bcb66/scratchpad/qb.json", "--quiet"], capture_output=True, text=True)
print(r.returncode, (r.stdout + r.stderr)[-400:])
