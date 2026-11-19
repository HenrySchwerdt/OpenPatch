"""Privacy pass over committed outputs: no absolute local paths, no personal names; STEP author/organisation = OpenPatch project."""
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ABS = re.compile(r"(/" + r"home/[^\"'\s,)]*|/" + r"Users/[^\"'\s,)]*)")


def main() -> None:
    n = 0
    for f in HERE.rglob("*"):
        if not f.is_file() or f.suffix not in (".step", ".json"):
            continue
        t = f.read_text(errors="ignore")
        o = t
        if f.suffix == ".step":
            hdr = "FILE_NAME('%s','',('OpenPatch project'),('OpenPatch project'),'SolidCraft','SolidCraft','');\n" % f.name
            t = re.sub(r"FILE_NAME\(.*?\);\n", lambda m: hdr, t, count=1, flags=re.S)
        elif f.name.endswith(".script.json"):
            t = re.sub(r'"path": "[^"]*/([^/"]+)"', r'"path": "\1"', t)
        t = ABS.sub("<local path>", t)
        if t != o:
            f.write_text(t)
            n += 1
    print("sanitized", n)


if __name__ == "__main__":
    sys.exit(main())
