#!/usr/bin/env python3
"""Assembly-feasibility and DFM checker for the OpenPatch bench pod (check.py only checks the final assembled state).

  python3 check_assembly.py                      # OP-100 (the current bench pod), writes out/bench/assembly-check/REPORT.md
  python3 check_assembly.py --sizes OP-70 OP-100 OP-200
  python3 check_assembly.py --only paths|access|dfm|fits    # run one section
  python3 check_assembly.py --step 0.25          # coarser insertion sweep (default 0.1 mm)
  python3 check_assembly.py --refresh            # re-export the meshes from the .sc even if cached
  python3 check.py --variant bench --assembly    # same, from check.py

What it does (see ASSEMBLY-CHECK.md):
  1. paths   - replays assembly_sequence.json: every part moves along its insertion path in small increments from outside to its
               CAD position; boolean-intersection volume against the parts already assembled; blocked paths, elastic engagement
               (snap arms: required deflection and strain), press-fit zones; for a blocked step an automatic search for any feasible path.
  2. access  - tool and finger access: screwdriver (tip / shaft / handle) along every screw axis, tweezer cone for small parts, FFC/ZIF latch.
  3. dfm     - wall thickness (inward ray casting), smallest hole/channel/slot (outward ray casting), CNC corner radius and pocket depth
               on the order STLs, against dfm_rules.json (JLC3DP SLA / MJF, CNC).
  4. fits    - every mating pair: nominal gap from the CAD, Monte Carlo with process sigma, probability fit / too loose / too tight,
               post-processing flags and whether the build guide mentions them.

Geometry is read generically: per-body meshes are exported from out/bench/<size>.sc with SolidCraft (cached by hash), mech/layout JSON and
the order STLs in out/bench/fab/.  No CAD file is edited.  Exit code 1 if a documented step is blocked, access fails, a part cannot be made
as drawn, or a fit has a high probability of failing (thresholds in dfm_rules.json).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
RULES_FILE = HERE / "dfm_rules.json"
SEQ_FILE = HERE / "assembly_sequence.json"
SEQ_FILE_V010 = HERE / "assembly_sequence_v010.json"


def seq_path(outdir: Path) -> Path:
    """The v0.1.0 integrated pod (out/v010, params.used.json carries `v010_pod`) has its own build order; the bench pod keeps assembly_sequence.json."""
    pu = Path(outdir) / "params.used.json"
    try:
        if pu.exists() and json.loads(pu.read_text()).get("v010_pod"):
            return SEQ_FILE_V010
    except Exception:       # noqa: BLE001
        pass
    return SEQ_FILE


def is_v010(outdir: Path) -> bool:
    return seq_path(outdir) == SEQ_FILE_V010
EPS_VOL = 1e-4            # mm3, same as check.py MIN_OVERLAP_MM3


def _need(mod: str):
    try:
        return __import__(mod)
    except ImportError:
        sys.exit(f"missing python package '{mod}': pip install trimesh numpy scipy shapely rtree manifold3d embreex matplotlib")


trimesh = _need("trimesh")
mf = _need("manifold3d")
shapely_geom = _need("shapely.geometry")
from shapely.geometry import LineString, Point  # noqa: E402
from shapely.ops import unary_union  # noqa: E402


# ------------------------------------------------------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------------------------------------------------------
def find_cli() -> str:
    for c in ("/usr/local/bin/solidcraft-cli", "/Applications/SolidCraft.app/Contents/MacOS/solidcraft-cli"):
        if Path(c).exists():
            return c
    sys.exit("solidcraft-cli not found")


def jload(p: Path) -> dict:
    return json.loads(p.read_text())


AX = {"X": np.array([1.0, 0, 0]), "Y": np.array([0, 1.0, 0]), "Z": np.array([0, 0, 1.0])}
AXI = {"X": 0, "Y": 1, "Z": 2}


class Env:
    """Evaluation context for expressions in the sequence file (L = mech.json, P = params, B = body bbox lookup)."""

    def __init__(self, mech: dict, params: dict, model: "Model"):
        self.ns = {"L": mech, "P": params, "min": min, "max": max, "abs": abs, "sqrt": math.sqrt, "B": model.bb}

    def val(self, x):
        if isinstance(x, str):
            return float(eval(x, {"__builtins__": {}}, self.ns))
        return float(x)

    def vec(self, v):
        return np.array([self.val(c) for c in v], float)


# ------------------------------------------------------------------------------------------------------------------------------
# geometry: per-body meshes from the assembly .sc (cached), manifold conversion, boolean helpers
# ------------------------------------------------------------------------------------------------------------------------------
class Model:
    def __init__(self, outdir: Path, size: str, quality: str = "standard", refresh: bool = False):
        self.outdir, self.size = outdir, size
        self.sc = outdir / f"{size}.sc"
        self.mdir = outdir / "assembly-check" / "meshes" / size
        self.mech = jload(outdir / f"{size}.mech.json")
        self.layout = jload(outdir / f"{size}.layout.json") if (outdir / f"{size}.layout.json").exists() else {}
        pu = outdir / "params.used.json"
        self.params = jload(pu if pu.exists() else HERE / "params.json")
        self.quality = quality
        self.mesh: dict[str, trimesh.Trimesh] = {}
        self._man: dict[str, object] = {}
        self._export(refresh)
        for f in sorted(self.mdir.glob("*.stl")):
            m = trimesh.load(f, force="mesh")
            m.merge_vertices()
            self.mesh[f.stem] = m

    def _export(self, refresh: bool) -> None:
        self.mdir.mkdir(parents=True, exist_ok=True)
        man = self.mdir / "manifest.json"
        sha = hashlib.sha256(self.sc.read_bytes()).hexdigest()
        if not refresh and man.exists():
            d = jload(man)
            if d.get("sha256") == sha and d.get("quality") == self.quality and all((self.mdir / f"{n}.stl").exists() for n in d["bodies"]):
                return
        cli = find_cli()
        print(f"[{self.size}] exporting per-body meshes from {self.sc.name} (SolidCraft, ~2 min, cached afterwards)", flush=True)
        tmp = self.mdir / "_measure.json"
        tmp.write_text(json.dumps([{"command": "inspect.measure", "params": {}}]))
        r = subprocess.run([cli, "run", str(tmp), "--in", str(self.sc), "--results", "--quiet"], capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit(r.stdout + r.stderr)
        names = [b["name"] for b in next(x for x in json.loads(r.stdout) if "bodies" in x)["bodies"]]
        for f in self.mdir.glob("*.stl"):
            f.unlink()
        cmds = [{"command": "file.export_stl", "params": {"path": str(self.mdir / f"{n}.stl"), "bodies": [n], "quality": self.quality}} for n in names]
        tmp.write_text(json.dumps(cmds))
        r = subprocess.run([cli, "run", str(tmp), "--in", str(self.sc), "--quiet"], capture_output=True, text=True)
        tmp.unlink(missing_ok=True)
        if r.returncode != 0:
            sys.exit(r.stdout + r.stderr)
        man.write_text(json.dumps({"sha256": sha, "quality": self.quality, "bodies": names}, indent=1))

    # -- bbox / manifold ------------------------------------------------------------------------------------------------------
    def has(self, n: str) -> bool:
        return n in self.mesh

    def bb(self, n: str, which: str, axis: str) -> float:
        b = self.mesh[n].bounds
        return float(b[0 if which == "min" else 1][AXI[axis]])

    def man(self, n: str):
        if n not in self._man:
            m = self.mesh[n]
            mm = mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))
            if mm.status() != mf.Error.NoError:
                raise RuntimeError(f"body '{n}' is not a valid manifold for boolean checks: {mm.status()}")
            self._man[n] = mm
        return self._man[n]

    def union(self, names: list[str]):
        ms = [self.man(n) for n in names]
        return ms[0] if len(ms) == 1 else mf.Manifold.batch_boolean(ms, mf.OpType.Add)

    def bounds_of(self, names: list[str]) -> np.ndarray:
        b = np.array([self.mesh[n].bounds for n in names])
        return np.array([b[:, 0].min(0), b[:, 1].max(0)])


def man_bbox(m) -> np.ndarray:
    b = m.bounding_box()
    return np.array([b[:3], b[3:]])


def box_man(lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    return mf.Manifold.cube(tuple(hi - lo)).translate(tuple(lo))


def orient(m, direction: np.ndarray):
    """Rotate a manifold built along +Z so that +Z points along `direction` (about the origin)."""
    d = np.asarray(direction, float)
    d = d / np.linalg.norm(d)
    T = trimesh.geometry.align_vectors([0, 0, 1], d)
    return m.transform(T[:3, :])


def tr(m, v):
    return m.translate(tuple(float(x) for x in v))


# ------------------------------------------------------------------------------------------------------------------------------
# 1. assembly sequence: path sweep
# ------------------------------------------------------------------------------------------------------------------------------
class Sequencer:
    def __init__(self, M: Model, seq: dict, rules: dict, step: float):
        self.M, self.seq, self.rules, self.step = M, seq, rules, step
        self.env = Env(M.mech, M.params, M)
        self.ctx_parts: dict[str, list[str]] = {}       # bodies assembled so far per context
        self.results: list[dict] = []
        self.snap_before: dict[str, list[str]] = {}      # bodies present (excluding the moving ones) before each step
        self.snap_after: dict[str, list[str]] = {}       # bodies present in the step's context after it
        for c, d in seq["contexts"].items():
            self.ctx_parts[c] = [b for b in d["base"] if M.has(b)]

    # expand "@ctx" tokens, drop bodies that do not exist in this CAD
    def expand(self, parts: list[str]) -> list[str]:
        out: list[str] = []
        for p in parts:
            out += self.ctx_parts[p[1:]] if p.startswith("@") else [p]
        return [p for p in out if self.M.has(p)]

    def path_vectors(self, path: list[dict]) -> list[tuple[np.ndarray, float]]:
        segs = []
        for s in path:
            d = self.env.vec(s["dir"])
            d = d / np.linalg.norm(d)
            segs.append((d, self.env.val(s["dist"])))
        return segs

    @staticmethod
    def offsets(segs, step: float) -> list[tuple[float, np.ndarray]]:
        """(s, offset) with s = path length still to go to the CAD position (0 = final); offset = pose - final pose."""
        total = sum(d for _, d in segs)
        out = []
        n = int(round(total / step))
        for k in range(n, -1, -1):
            s = min(k * step, total)
            rem, off = s, np.zeros(3)
            for d, ln in reversed(segs):          # last segment ends at the CAD position
                take = min(rem, ln)
                off -= d * take
                rem -= take
                if rem <= 1e-12:
                    break
            out.append((s, off))
        return out

    @staticmethod
    def pose_offset(segs, s: float) -> np.ndarray:
        rem, off = s, np.zeros(3)
        for d, ln in reversed(segs):
            take = min(rem, ln)
            off -= d * take
            rem -= take
            if rem <= 1e-12:
                break
        return off

    def sweep(self, mover: list[str], fixed: list[str], segs, tol_pairs: dict, step: float | None = None, want_depth: dict | None = None, shifts: dict | None = None) -> dict:
        """Sweep `mover` along `segs`; return per fixed body {max_vol, s_of_max, first_s, hits:[(s,vol)], depth} (volumes in mm3)."""
        M, step = self.M, step or self.step
        mov = M.union(mover)
        mb = man_bbox(mov)
        poses = self.offsets(segs, step)
        offs = np.array([o for _, o in poses])
        lo, hi = mb[0] + offs.min(0) - 0.3, mb[1] + offs.max(0) + 0.3
        res: dict[str, dict] = {}
        for f in fixed:
            sv = np.asarray((shifts or {}).get(f, (0.0, 0.0, 0.0)), float)       # a part that is in a PARKED pose while this step runs (e.g. the screw retracted)
            fb = M.mesh[f].bounds + sv
            if np.any(fb[1] < lo) or np.any(fb[0] > hi):
                continue
            fc = (tr(M.man(f), sv) if np.any(sv) else M.man(f)) ^ box_man(lo, hi)
            if fc.is_empty():
                continue
            rec = {"max_vol": 0.0, "s_max": None, "hits": [], "depth": {}}
            fcb = man_bbox(fc)
            for s, off in poses:
                if np.any(mb[1] + off < fcb[0]) or np.any(mb[0] + off > fcb[1]):
                    continue
                inter = tr(mov, off) ^ fc
                v = inter.volume()
                if v > EPS_VOL:
                    rec["hits"].append((round(s, 4), v))
                    if v > rec["max_vol"]:
                        rec["max_vol"], rec["s_max"] = v, s
                        ib = man_bbox(inter)
                        rec["bbox"] = ib.tolist()
                    if want_depth is not None and f in want_depth:
                        rec["depth"][round(s, 4)] = self.flex_extent(inter, want_depth[f])
            if rec["hits"]:
                res[f] = rec
        return res

    def flex_extent(self, inter, spec: dict) -> list[float]:
        """Overlap extent along the flex axis on each side of the centre line (upper bound of the required arm deflection)."""
        ax, c = AXI[spec["axis"]], self.env.val(spec["centre"])
        mesh = inter.to_mesh()
        v = np.asarray(mesh.vert_properties)[:, :3]
        out = []
        for side in (-1, 1):
            w = v[(v[:, ax] - c) * side > 0][:, ax]
            out.append(float(w.max() - w.min()) if len(w) else 0.0)
        return out

    # ------------------------------------------------------------------------------------------------------------------------------
    def run_step(self, st: dict, alt_search: bool = True) -> dict:
        M = self.M
        ctx = st["context"]
        mover = self.expand(st["parts"])
        present = [b for b in self.ctx_parts[ctx] if b not in mover]
        rec = {"id": st["id"], "title": st["title"], "guide": st.get("guide", ""), "context": ctx, "parts": mover, "tool": st.get("tool", ""),
               "present": len(present), "status": "OK", "notes": [], "events": [], "alternatives": []}
        if not mover:
            rec["status"], rec["notes"] = "SKIP", ["no body of this step exists in the CAD"]
            return rec
        self.snap_before[st["id"]] = list(present)
        segs = self.path_vectors(st["path"])
        rec["path"] = [{"dir": [round(float(x), 3) for x in d], "dist": round(l, 3)} for d, l in segs]
        eng = {tuple(e["pair"]): e for e in st.get("engages", [])}
        tol = {}
        for (a, b), e in eng.items():
            for m_ in mover:
                if a in (m_,) or a == "*":
                    tol[b] = e
                if b == m_:
                    tol[a] = e
        flex_spec = {}
        for e in st.get("engages", []):
            if e["kind"] == "snap":
                flex_spec[e["pair"][1]] = e["flex"]
        shifts = {k: self.env.vec(v) for k, v in st.get("present_offsets", {}).items()}
        res = self.sweep(mover, present, segs, tol, want_depth=flex_spec, shifts=shifts)
        blocked, engaged = [], []
        for f, r in res.items():
            e = tol.get(f)
            for s, v in r["hits"]:
                ok = False
                if e is not None:
                    if e["kind"] in ("snap", "stretch", "flexible"):
                        ok = True
                    else:
                        ok = s <= self.env.val(e.get("zone", 1.0)) + 1e-9
                if s == 0 and e is None:
                    ok = False
                if not ok:
                    blocked.append((s, f, v))
            if e is not None:
                zone_hits = [(s, v) for s, v in r["hits"] if e["kind"] in ("snap", "stretch", "flexible") or s <= self.env.val(e.get("zone", 1.0)) + 1e-9]
                if zone_hits:
                    ev = {"pair": [",".join(mover[:2]) + ("..." if len(mover) > 2 else ""), f], "kind": e["kind"], "max_overlap_mm3": round(max(v for _, v in zone_hits), 4),
                          "from_s": max(s for s, _ in zone_hits), "to_s": min(s for s, _ in zone_hits)}
                    if e["kind"] == "snap" and r["depth"]:
                        worst = [max(d[i] for d in r["depth"].values()) for i in (0, 1)]
                        ev["required_deflection_mm"] = [round(x, 3) for x in worst]
                        ev.update(self.snap_strain(e, max(worst)))
                    engaged.append(ev)
        rec["events"] = engaged
        if blocked:
            blocked.sort(key=lambda t: -t[0])
            by: dict[str, dict] = {}
            for s, f, v in blocked:
                d = by.setdefault(f, {"body": f, "first_s": s, "last_s": s, "max_mm3": 0.0, "at_s": res[f]["s_max"], "offset": [round(float(x), 4) for x in self.pose_offset(segs, res[f]["s_max"])], "bbox": [[round(x, 2) for x in b] for b in res[f]["bbox"]]})
                d["last_s"] = min(d["last_s"], s)
                d["max_mm3"] = max(d["max_mm3"], v)
            rec["blocked_by"] = sorted(by.values(), key=lambda d: -d["first_s"])
            rec["status"] = "BLOCKED"
            if all(d["first_s"] == 0 for d in rec["blocked_by"]):
                rec["status"] = "FINAL-INTERFERENCE"
            rec["notes"].append("first collision at s = %.2f mm before the CAD position with %s" % (rec["blocked_by"][0]["first_s"], rec["blocked_by"][0]["body"]))
            if alt_search and rec["status"] == "BLOCKED" and st.get("search", True):
                rec["alternatives"] = self.find_alternatives(mover, present, segs)
        # elastic strain note for ring stretch handled in the fits section
        self.ctx_parts[ctx] += [m for m in mover if m not in self.ctx_parts[ctx]]
        self.snap_after[st["id"]] = list(self.ctx_parts[ctx])
        return rec

    def snap_strain(self, e: dict, delta: float) -> dict:
        D = self.M.mech["dock"]
        t, L = D["arm_t"], D["flex_len"]
        eps = 1.5 * t * delta / L ** 2          # cantilever with tip load: eps = 3 t d / (2 L^2)
        mat = e.get("material", "PA12_MJF")
        lim = self.rules["materials"][mat]["snap_strain_allow"]
        return {"arm_t": t, "arm_len": L, "strain_pct": round(eps * 100, 2), "material": mat, "limit_pct": lim * 100, "strain_ok": eps <= lim,
                "cad_travel_mm": round(D["travel"], 3), "cad_strain_pct": round(D["arm_strain"] * 100, 2)}

    # candidate path families for a blocked step: straight from 6 directions, lift-and-slide L paths
    def find_alternatives(self, mover, present, segs) -> list[dict]:
        M = self.M
        mb = M.bounds_of(mover)
        size = mb[1] - mb[0]
        lead = float(sum(d for _, d in segs))
        cands = []
        for ax, v in AX.items():
            for sg in (-1, 1):
                cands.append((f"straight {'+' if sg > 0 else '-'}{ax}", [(sg * v, max(lead, 60.0))]))
        dirs = [(f"{'+' if sg > 0 else '-'}{ax}", sg * v) for ax, v in AX.items() for sg in (-1, 1)]
        for ln in (1.0, 3.0, 8.0):                      # approach along d1, then slide the last `ln` mm along d2 (perpendicular)
            for n1, d1 in dirs:
                for n2, d2 in dirs:
                    if abs(float(np.dot(d1, d2))) > 0.1:
                        continue
                    h = 12.0 + float(size @ np.abs(d1))
                    cands.append((f"move {n1} {h:.0f} mm, then slide {n2} the last {ln:g} mm", [(d1, h), (d2, ln)]))
        out = []
        for name, sg_ in cands:
            # path semantic: list of (dir, dist) in assembly order ending at CAD pose; for "straight" the single seg ends at CAD pose
            try:
                r = self.sweep(mover, present, sg_, {}, step=0.5)
            except Exception as ex:           # noqa: BLE001
                continue
            bad = [(h[0], f) for f, rr in r.items() for h in rr["hits"] if h[0] > 0.0]
            if not bad:
                out.append({"path": name, "free_at_0.5mm_step": True})
                break
        return out

    # ------------------------------------------------------------------------------------------------------------------------------
    def run_all(self) -> list[dict]:
        out = []
        for st in self.seq["steps"]:
            t0 = time.time()
            r = self.run_step(st)
            r["seconds"] = round(time.time() - t0, 1)
            print(f"  {r['id']:5} {r['status']:18} {r['title'][:70]}  ({r['seconds']} s)", flush=True)
            out.append(r)
        self.results = out
        return out


# ------------------------------------------------------------------------------------------------------------------------------
# 2. tool and finger access
# ------------------------------------------------------------------------------------------------------------------------------
class Access:
    def __init__(self, S: Sequencer):
        self.S, self.M, self.rules, self.seq = S, S.M, S.rules, S.seq
        self.tools = self.seq["tools"]

    def present_union(self, names: list[str], lo, hi):
        ms = []
        for n in names:
            b = self.M.mesh[n].bounds
            if np.any(b[1] < lo) or np.any(b[0] > hi):
                continue
            c = self.M.man(n) ^ box_man(lo, hi)
            if not c.is_empty():
                ms.append((n, c))
        return ms

    @staticmethod
    def hits(tool, parts) -> dict:
        out = {}
        for n, c in parts:
            v = (tool ^ c).volume()
            if v > EPS_VOL:
                out[n] = round(v, 4)
        return out

    # -- tweezers / push cone -------------------------------------------------------------------------------------------------
    def tweezers(self, step_rec: dict, st: dict) -> dict:
        tw = self.tools["tweezers"]
        mover = step_rec["parts"]
        present = self.S.snap_before[st["id"]]
        segs = self.S.path_vectors(st["path"])
        d = segs[-1][0]
        a = -d                                          # tweezers come from behind the part
        mb = self.M.bounds_of(mover)
        ctr = (mb[0] + mb[1]) / 2
        k = int(np.argmax(np.abs(a)))
        ext = mb[1][k] if a[k] > 0 else mb[0][k]
        # candidate grip points on the trailing face of the part: the surface point nearest the bbox centre (rings and bores are empty
        # in the middle) and the four rim extremes across the face
        vs = np.vstack([self.M.mesh[p].vertices for p in mover])
        face = vs[np.abs(vs[:, k] - ext) < 0.06]
        u = np.cross(a, [1, 0, 0]) if abs(a[0]) < 0.9 else np.cross(a, [0, 1, 0])
        u /= np.linalg.norm(u)
        w_ = np.cross(a, u)
        cands = [face[int(np.argmin(np.linalg.norm(face - np.where(np.arange(3) == k, ext, ctr), axis=1)))]]
        for vec in (u, -u, w_, -w_):
            cands.append(face[int(np.argmax(face @ vec))])
        L, r0 = tw["length"], tw["tip_d"] / 2
        need = tw["cone_half_angle_deg"]
        res = {"id": st["id"], "kind": "tweezers", "title": st["title"], "axis": [round(float(x), 2) for x in a]}
        best_all, found_all = None, None
        for c0 in cands:
            apex = c0 + a * 0.05
            parts = self.present_union([p for p in present if p not in mover], apex - L - 1, apex + L + 1)
            best, found = (-1.0, 0.0, 0.0, {}), None
            for tilt in (0, 15, 30, tw["max_tilt_deg"]):
                for az in ((0.0,) if tilt == 0 else (0, 45, 90, 135, 180, 225, 270, 315)):
                    ad = math.cos(math.radians(tilt)) * a + math.sin(math.radians(tilt)) * (math.cos(math.radians(az)) * u + math.sin(math.radians(az)) * w_)
                    free, blk = -1.0, {}
                    for ang in (0, 5, need, 20, 30):
                        cone = tr(orient(mf.Manifold.cylinder(L, r0, r0 + L * math.tan(math.radians(ang)), 24), ad), apex)
                        h = self.hits(cone, parts)
                        if h:
                            blk = h
                            break
                        free = ang
                    if free > best[0] or (free == best[0] and tilt < best[1]):
                        best = (free, tilt, az, blk)
                    if free >= need and found is None:
                        found = (tilt, az, ad)
            if best_all is None or best[0] > best_all[0][0]:
                best_all = (best, apex)
            if found:
                found_all = (found, apex)
                break
        best, apex = best_all
        res["apex"] = [round(float(x), 2) for x in apex]
        res["best_tilt_deg"] = best[1]
        if found_all:
            found, apex = found_all
            res["apex"] = [round(float(x), 2) for x in apex]
            res["approach"] = f"free at {found[0]} deg tilt from the insertion axis"
        cone = tr(orient(mf.Manifold.cylinder(L, r0, r0 + L * math.tan(math.radians(need)), 24), found_all[0][2] if found_all else a), apex)
        res["_tool"], res["_centre"] = man_to_tri(cone), apex
        res["max_free_half_angle_deg"] = best[0]
        res["required_deg"] = need
        res["blockers"] = best[3]
        res["status"] = "OK" if found_all else ("TIGHT" if best[0] >= 0 else "BLOCKED")
        return res

    # -- screws ------------------------------------------------------------------------------------------------------------------
    def screw_positions(self) -> list[dict]:
        out = []
        for sc in self.seq["screws"]:
            if sc["source"] == "mech":
                s = self.M.mech["screws"][sc["index"]]
                xy = (s["x"], s["y"])
            elif sc["source"] == "xy":
                xy = tuple(self.S.env.val(c) for c in sc["xy"])
            else:
                xy = tuple(self.M.layout["mounting"]["screw"]["center_pod_mm"])
            out.append({**sc, "xy": xy})
        return out

    def seat_z(self, present: list[str], xy, head_h: float) -> float | None:
        ang = np.linspace(0, 2 * math.pi, 8, endpoint=False)
        o = np.array([[xy[0] + 1.0 * math.cos(t), xy[1] + 1.0 * math.sin(t), 40.0] for t in ang])
        d = np.tile([0, 0, -1.0], (len(o), 1))
        zs = []
        for n in present:
            m = self.M.mesh[n]
            loc, ir, _ = m.ray.intersects_location(o, d, multiple_hits=False)
            for z, i in zip(loc[:, 2], ir):
                zs.append((z, n))
        if not zs:
            return None
        zs.sort(reverse=True)
        top = [z for z, _ in zs if z >= zs[0][0] - 0.05]       # first surface met from above at most of the ring
        return float(np.median(top)) + head_h

    def driver(self, sc: dict) -> dict:
        T = self.tools["driver"]
        head_h = self.tools["screw"][sc["kind"]]["head_h"]
        present = self.S.snap_after[sc["after"]]
        xy = sc["xy"]
        zs = self.seat_z(present, xy, 0.0)
        res = {"id": sc["id"], "kind": "driver", "title": sc["title"], "xy": [round(xy[0], 2), round(xy[1], 2)], "after": sc["after"]}
        if zs is None:
            res.update(status="BLOCKED", note="no surface under the screw axis")
            return res
        z0 = zs + head_h
        res["seat_z"] = round(z0, 2)
        lo, hi = np.array([xy[0] - 8, xy[1] - 8, z0 - 3.0]), np.array([xy[0] + 8, xy[1] + 8, z0 + 60])
        parts = self.present_union(present, lo, hi)
        # the screw sits in the counterbore: head seat bodies that the tool tip touches are allowed only below z0 (tip is above z0)

        def tool(tip_d, tip_len, tilt=0.0, az=0.0):
            segs = [(tip_d, tip_len), (T["shaft_d"], T["shaft_len"] - tip_len), (T["handle_d"], T["handle_len"])]
            z, ms = 0.0, []
            for dia, ln in segs:
                ms.append(mf.Manifold.cylinder(ln, dia / 2, dia / 2, 32).translate((0, 0, z)))
                z += ln
            t = mf.Manifold.batch_boolean(ms, mf.OpType.Add)
            if tilt:
                t = t.rotate((0, tilt, 0)).rotate((0, 0, az))
            return t.translate((xy[0], xy[1], z0))

        out = {}
        for tip_d in (1.5, 2.0):
            free = -1.0
            blockers = {}
            for tilt in (0, 2.5, 5, 7.5, 10, 15, 20):
                bad = {}
                for az in ((0.0,) if tilt == 0 else range(0, 360, 45)):
                    bad.update(self.hits(tool(tip_d, T["tip_len"], tilt, float(az)), parts))
                if bad:
                    blockers = bad
                    break
                free = tilt
            out[tip_d] = {"free_tilt_deg": free, "blockers": blockers}
        # minimum tip length that clears an axial driver
        lmin = None
        for L in np.arange(0.25, 12.01, 0.25):
            if not self.hits(tool(1.5, float(L)), parts):
                lmin = float(L)
                break
        res["tip_1.5"], res["tip_2.0"], res["min_tip_len_mm"] = out[1.5], out[2.0], lmin
        res["_tool"], res["_centre"] = man_to_tri(tool(2.0, T["tip_len"])), np.array([xy[0], xy[1], z0])
        worst = min(out[1.5]["free_tilt_deg"], out[2.0]["free_tilt_deg"])
        need = self.rules["thresholds"]["min_free_tilt_driver_deg"]
        res["status"] = "OK" if worst >= need else ("TIGHT" if worst >= 0 else "BLOCKED")
        res["required_tilt_deg"] = need
        return res

    # -- ZIF latch -----------------------------------------------------------------------------------------------------------
    def zif(self, step_rec: dict, st: dict) -> dict:
        present = self.S.snap_before[st["id"]]
        res = {"id": st["id"], "kind": "zif", "title": "FFC ZIF flip-lock actuator and cable entry"}
        if not self.M.has("ffc_conn"):
            res["status"] = "SKIP"
            return res
        cb = self.M.mesh["ffc_conn"].bounds
        # lever: hinge at the cable-entry (+X) side; nail/tweezer tip needs the strip above the connector rear edge plus 3 mm swing
        lever = box_man([cb[1][0] - 1.0, cb[0][1], cb[1][2]], [cb[1][0] + 2.5, cb[1][1], cb[1][2] + 3.0])
        parts = self.present_union([p for p in present if p != "ffc_conn"], cb[0] - 6, cb[1] + 6)
        h = self.hits(lever, parts)
        res["lever_box"] = [[round(float(x), 2) for x in lever_b] for lever_b in man_bbox(lever)]
        res["blockers_lever"] = h
        # tweezer tip onto the lever from above, +-30 deg in the cable direction
        apex = np.array([cb[1][0] + 0.5, (cb[0][1] + cb[1][1]) / 2, cb[1][2]])
        free = -1
        for ang in (0, 15, 30, 45):
            a = np.array([math.sin(math.radians(ang)), 0, math.cos(math.radians(ang))])
            cone = tr(orient(mf.Manifold.cylinder(12, 0.3, 0.3, 16), a), apex)
            if self.hits(cone, parts):
                break
            free = ang
        res["free_approach_deg"] = free
        res["status"] = "OK" if (not h and free >= 30) else ("TIGHT" if (not h and free >= 0) else "BLOCKED")
        return res

    def run_all(self, step_recs: list[dict]) -> list[dict]:
        out = []
        by = {r["id"]: r for r in step_recs}
        for st in self.seq["steps"]:
            r = by.get(st["id"])
            if not r or r["status"] == "SKIP":
                continue
            acc = st.get("access")
            if acc == "tweezers":
                out.append(self.tweezers(r, st))
            elif acc == "zif":
                out.append(self.zif(r, st))
        for sc in self.screw_positions():
            if sc["after"] in self.S.snap_after:
                out.append(self.driver(sc))
        for r in out:
            print(f"  access {r['id']:9} {r['status']:8} {r.get('title', '')[:60]}", flush=True)
        return out


# ------------------------------------------------------------------------------------------------------------------------------
# 3. DFM: measure the order files against dfm_rules.json
# ------------------------------------------------------------------------------------------------------------------------------
def interp_table(tab: list, x: float) -> float:
    xs, ys = [t[0] for t in tab], [t[1] for t in tab]
    return float(np.interp(x, xs, ys))


def proc_of(text: str) -> str:
    t = text.strip()
    if t.startswith("MJF"):
        return "MJF"
    if t.startswith("SLA"):
        return "SLA"
    if "CNC" in t:
        return "CNC_PP"
    return "SLA"


class DFM:
    def __init__(self, M: Model, rules: dict, outdir: Path, size: str, n_samples: int = 60000):
        self.M, self.rules, self.outdir, self.size, self.n = M, rules, outdir, size, n_samples
        self.fab = outdir / "fab"

    # -- which files are ordered, with which process -----------------------------------------------------------------------
    def order_list(self) -> list[dict]:
        out = []
        man = self.fab / "MANIFEST.csv"
        if not man.exists():
            return out
        for row in csv.DictReader(man.open()):
            f = row["file"]
            if f.startswith(self.size + "/"):
                out.append({"name": Path(f).stem, "file": self.fab / f, "process": proc_of(row["process"]), "qty": row["qty"], "kind": "order"})
            elif f.startswith("mould/"):
                out.append({"name": "mould_" + Path(f).stem.replace("mould_", ""), "file": self.fab / f, "process": "SLA", "qty": row["qty"], "kind": "order"})
        for stem, proc in (("insert_v01", "SLA"), ("insert_v10", "SLA"), ("dock_fixture", "MJF")):
            f = self.fab / "dock-inserts" / f"{stem}.stl"
            if f.exists():
                out.append({"name": stem, "file": f, "process": proc, "qty": "-", "kind": "order"})
        for f in sorted((self.fab / "reservoir-cnc").glob("*_reservoir_cnc.step")):
            out.append({"name": f.stem, "file": f, "process": "CNC_PP", "qty": "2", "kind": "cnc", "size": f.stem.split("_")[0]})
        return out

    def load(self, item: dict):
        f = item["file"]
        if f.suffix == ".step":
            stl = self.outdir / "assembly-check" / "meshes" / "_cnc" / (f.stem + ".stl")
            if not stl.exists():
                stl.parent.mkdir(parents=True, exist_ok=True)
                r = subprocess.run([find_cli(), "run", str(f), "--out", str(stl), "--quality", "fine", "--quiet"], capture_output=True, text=True)
                if r.returncode != 0 or not stl.exists():
                    return None
            f = stl
        m = trimesh.load(f, force="mesh")
        m.merge_vertices()
        return m

    # -- ray casting -------------------------------------------------------------------------------------------------------
    def rays(self, m, origins, dirs, max_d: float):
        loc, ir, itri = m.ray.intersects_location(origins, dirs, multiple_hits=False)
        dist = np.full(len(origins), np.inf)
        ok = np.zeros(len(origins), bool)
        if len(ir):
            d = np.linalg.norm(loc - origins[ir], axis=1)
            facing = np.einsum("ij,ij->i", m.face_normals[itri], dirs[ir])
            dist[ir] = d
            ok[ir] = facing
        return dist, loc, ir, itri

    def analyse(self, item: dict) -> dict:
        m = self.load(item)
        if m is None:
            return {"name": item["name"], "error": "could not load mesh"}
        proc = item["process"]
        R = self.rules["processes"][proc]
        ext = np.sort(m.extents)[::-1]
        footprint = float(math.sqrt(ext[0] * ext[1]))
        wall_vendor = interp_table(R["wall"]["table_by_footprint_mm"], footprint)
        wall_floor = R["wall"]["hard_floor"]
        rec = {"name": item["name"], "process": proc, "qty": item["qty"], "file": str(item["file"].relative_to(self.outdir.parent.parent)) if item["file"].is_relative_to(self.outdir.parent.parent) else str(item["file"]),
               "extents": [round(float(x), 2) for x in m.extents], "faces": int(len(m.faces)), "watertight": bool(m.is_watertight), "footprint_mm": round(footprint, 1),
               "wall_vendor": round(wall_vendor, 2), "wall_floor": wall_floor, "violations": []}
        rng = np.random.default_rng(7)
        pts, fi = trimesh.sample.sample_surface(m, self.n, seed=int(rng.integers(1 << 30)))
        nrm = m.face_normals[fi]
        # --- wall thickness: shape-diameter function = median of 7 inward rays (axis + 6 at 20 deg) to the first opposite-facing surface.
        #     (a single normal ray reports 0 at tessellated fillets / knife edges that are no real wall)
        t_ = np.cross(nrm, [1.0, 0.0, 0.0])
        bad = np.linalg.norm(t_, axis=1) < 0.3
        t_[bad] = np.cross(nrm[bad], [0.0, 1.0, 0.0])
        t_ /= np.linalg.norm(t_, axis=1)[:, None]
        b_ = np.cross(nrm, t_)
        ray_d = [-nrm]
        for k in range(6):
            ang = k * math.pi / 3
            ray_d.append(-nrm * math.cos(math.radians(20)) + math.sin(math.radians(20)) * (math.cos(ang) * t_ + math.sin(ang) * b_))
        D_ = np.full((len(ray_d), len(pts)), np.nan)
        for k, dd in enumerate(ray_d):
            dist, loc, ir, itri = self.rays(m, pts - nrm * 1e-3, dd, 50)
            if len(ir):
                fac = np.einsum("ij,ij->i", m.face_normals[itri], dd[ir]) > 0.5
                D_[k, ir[fac]] = dist[ir[fac]]
        nvalid = np.sum(np.isfinite(D_), axis=0)
        thick = np.where(nvalid >= 4, np.nanmedian(np.where(np.isfinite(D_), D_, np.nan), axis=0), np.inf)
        valid = np.isfinite(thick)
        rec["wall_min"] = float(np.min(thick[valid])) if valid.any() else None
        rec["wall_p01"] = float(np.percentile(thick[valid], 1)) if valid.any() else None
        rec["wall_p05"] = float(np.percentile(thick[valid], 5)) if valid.any() else None
        area_frac_floor = float(np.mean(thick[valid] < wall_floor)) if valid.any() else 0
        area_frac_vendor = float(np.mean(thick[valid] < wall_vendor)) if valid.any() else 0
        rec["area_below_floor_pct"], rec["area_below_vendor_pct"] = round(100 * area_frac_floor, 2), round(100 * area_frac_vendor, 1)
        rec["wall_clusters"] = self.cluster(pts, thick, nrm, wall_vendor, valid, wall_floor)
        # --- voids (holes, channels, slots): outward rays
        vdist, vloc, vir, vitri = self.rays(m, pts + nrm * 1e-3, nrm, 6.0)
        vf = np.zeros(len(pts), bool)
        if len(vir):
            vf[vir] = np.einsum("ij,ij->i", m.face_normals[vitri], nrm[vir]) < -0.8
        width = np.where(vf, vdist, np.inf)
        rec["holes"] = self.holes(m, pts, nrm, width, R, proc)
        rec["_pts"], rec["_thick"] = pts, thick            # for plotting (removed before JSON dump)
        # --- verdicts
        for c in rec["wall_clusters"]:
            if c["min_mm"] < wall_floor - 0.02:
                if c["min_mm"] < 0.02:
                    sev = "FAIL" if c["n"] >= 100 else "WARN"
                    rec["violations"].append({"sev": sev, "what": f"zero-thickness skin ({c['min_mm']:.3f} mm): coincident or tangent faces, e.g. a bore tangent to an outer face; the slicer will drop or crack it ({proc})", "where": c["where"], "n": c["n"]})
                else:
                    rec["violations"].append({"sev": "FAIL", "what": f"wall {c['min_mm']:.2f} mm < hard floor {wall_floor} mm ({proc})", "where": c["where"], "n": c["n"]})
        if rec["area_below_vendor_pct"] > 0:
            rec["violations"].append({"sev": "WARN", "what": f"{rec['area_below_vendor_pct']} % of the wall samples thinner than the vendor value {wall_vendor:.2f} mm for a {footprint:.0f} mm part (min {rec['wall_min']:.2f} mm)", "where": ""})
        for h in rec["holes"]:
            if h["verdict"] != "OK":
                rec["violations"].append({"sev": h["verdict"], "what": h["text"], "where": h["where"]})
        if proc == "CNC_PP":
            rec["cnc"] = self.cnc(m, R)
            for v in rec["cnc"]["violations"]:
                rec["violations"].append(v)
        merged: dict = {}
        for v in rec["violations"]:
            key = (v["sev"], v["what"])
            if key in merged:
                merged[key]["places"] += 1
                if len(merged[key]["also"]) < 2:
                    merged[key]["also"].append(v["where"])
                merged[key]["n"] = merged[key].get("n", 0) + (v.get("n") or 0)
            else:
                merged[key] = dict(v, places=1, also=[])
        rec["violations"] = sorted(merged.values(), key=lambda v: ({"FAIL": 0, "WARN": 1}.get(v["sev"], 2)))
        rec["verdict"] = "FAIL" if any(v["sev"] == "FAIL" for v in rec["violations"]) else ("WARN" if rec["violations"] else "OK")
        return rec

    @staticmethod
    def cluster(pts, vals, nrm, limit, valid, floor, cell=1.0, top=14):
        sel = valid & (vals < limit)
        if not sel.any():
            return []
        idx = np.where(sel)[0]
        keys = {}
        for i in idx:
            k = tuple(np.floor(pts[i] / cell).astype(int))
            keys.setdefault(k, []).append(i)
        out = []
        for k, ii in keys.items():
            j = ii[int(np.argmin(vals[ii]))]
            if len(ii) < 6:
                continue
            out.append({"min_mm": float(vals[j]), "n": len(ii), "where": [round(float(x), 2) for x in pts[j]], "normal": [round(float(x), 2) for x in nrm[j]]})
        out.sort(key=lambda c: c["min_mm"])
        # merge neighbours of the same value into the top list
        return out[:top]

    def holes(self, m, pts, nrm, width, R, proc) -> list[dict]:
        cand = np.where((width < 3.2) & (width > 0.1))[0]
        if len(cand) == 0:
            return []
        mids = pts[cand] + nrm[cand] * width[cand, None] / 2
        keys = {}
        for n_, p in zip(cand, mids):
            keys.setdefault(tuple(np.floor(p / 0.5).astype(int)), []).append(n_)
        out = []
        dirs = []
        for th in np.linspace(0, math.pi, 12, endpoint=False):
            pass
        for k, ii in keys.items():
            if len(ii) < 6:
                continue
            w = float(np.median(width[ii]))
            c = np.mean(pts[ii] + nrm[ii] * width[ii, None] / 2, axis=0)
            out.append(self.void_shape(m, c, w, R, proc, len(ii)))
        out = [o for o in out if o]
        # merge near duplicates (same diameter, centres within 1 mm along any axis already handled by the grid): keep smallest per rounded (w, kind)
        out.sort(key=lambda o: o["width_mm"])
        uniq, seen = [], set()
        for o in out:
            key = (round(o["width_mm"], 1), o["kind"], tuple(o["axis"]), tuple(round(x / 3) for x in o["where"]))
            if key in seen:
                continue
            seen.add(key)
            uniq.append(o)
        return uniq[:12]

    def void_shape(self, m, c, w, R, proc, nsamples):
        # free length in 26 directions
        base = np.array([[x, y, z] for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)], float)
        base /= np.linalg.norm(base, axis=1)[:, None]
        o = np.tile(c, (len(base), 1))
        loc, ir, itri = m.ray.intersects_location(o, base, multiple_hits=False)
        free = np.full(len(base), np.inf)
        for i_, l_ in zip(ir, loc):
            free[i_] = np.linalg.norm(l_ - c)
        # sanity: the point must lie in a void (most rays hit an inward-facing surface)
        if np.isfinite(free).sum() < 6:
            axis_i = int(np.argmax(np.where(np.isfinite(free), free, 1e6)))
        axis_i = int(np.argmax(np.where(np.isfinite(free), free, 1e3)))
        # opposite pairs
        pair_len = {}
        for i, d in enumerate(base):
            j = int(np.argmin(np.linalg.norm(base + d, axis=1)))
            pair_len[i] = free[i] + free[j]
        lens = np.array([pair_len[i] for i in range(len(base))])
        axis_i = int(np.argmax(np.where(np.isfinite(lens), lens, 1e3)))
        ax = base[axis_i]
        # chords in the plane perpendicular to the axis
        u = np.cross(ax, [1, 0, 0]) if abs(ax[0]) < 0.9 else np.cross(ax, [0, 1, 0])
        u /= np.linalg.norm(u)
        v = np.cross(ax, u)
        chords = []
        for th in np.linspace(0, math.pi, 12, endpoint=False):
            d = math.cos(th) * u + math.sin(th) * v
            oo = np.array([c, c])
            dd = np.array([d, -d])
            loc2, ir2, _ = m.ray.intersects_location(oo, dd, multiple_hits=False)
            ln = [np.inf, np.inf]
            for i_, l_ in zip(ir2, loc2):
                ln[i_] = float(np.linalg.norm(l_ - c))
            chords.append(ln[0] + ln[1])
        chords = np.array(chords)
        finite = chords[np.isfinite(chords)]
        if len(finite) < 6:
            return None
        cmin, cmax = float(finite.min()), float(finite.max())
        if cmin > 3.4:
            return None
        rnd = cmax / cmin < 1.3
        # depth along the axis from the mid point: both directions, capped at the bounding box when open
        L = []
        for sg in (1, -1):
            l_ = free[axis_i] if sg == 1 else free[int(np.argmin(np.linalg.norm(base + ax, axis=1)))]
            L.append(l_)
        open_ends = int(sum(not np.isfinite(x) for x in L))
        depth = sum(x for x in L if np.isfinite(x))
        if open_ends == 2:
            depth = float(np.abs(m.extents @ np.abs(ax)))
        elif open_ends == 1:
            pass
        wv = cmin
        hr = R["hole"]
        kind = "hole" if rnd else "slot/channel"
        ratio = depth / wv if wv > 0 else 0
        verdict, text = "OK", ""
        vmin, floor_d = hr["vendor_min_dia"], hr["hard_floor_dia"]
        dr = hr.get("depth_max_ratio")
        if wv < floor_d - 0.03:
            verdict, text = "FAIL", f"{kind} width {wv:.2f} mm < hard floor {floor_d} mm ({proc}): cannot be reliably printed/machined as drawn; drill or wire it"
        elif wv < vmin - 1e-3:
            verdict, text = "WARN", f"{kind} width {wv:.2f} mm < vendor minimum {vmin} mm ({proc}); post-drill/ream it"
        if dr and rnd and ratio > dr * 1.0 and open_ends < 2 and wv < 4.0:
            sev = "FAIL" if (wv < vmin or ratio > 2 * dr) else "WARN"
            if verdict != "FAIL":
                verdict = sev
            text += ("; " if text else "") + f"depth/width {ratio:.1f} > {dr:.0f} (vendor hole table)" if text else f"{kind} {wv:.2f} mm wide, {depth:.1f} mm deep (ratio {ratio:.1f} > {dr:.0f}, vendor hole table)"
        if verdict == "OK":
            return {"width_mm": round(wv, 2), "kind": kind, "axis": [round(float(x), 2) for x in ax], "depth_mm": round(depth, 1), "where": [round(float(x), 2) for x in c], "verdict": "OK", "text": "", "n": nsamples, "open_ends": open_ends}
        return {"width_mm": round(wv, 2), "kind": kind, "axis": [round(float(x), 2) for x in ax], "depth_mm": round(depth, 1), "where": [round(float(x), 2) for x in c], "verdict": verdict, "text": text, "n": nsamples, "open_ends": open_ends}

    # -- CNC: internal corner radius and pocket depth --------------------------------------------------------------------
    def cnc(self, m, R) -> dict:
        out = {"violations": []}
        cr = R["corner"]
        tool_r = cr["tool_dia_available"] / 2
        # find the bore: the longest axis of the part is the bore axis (reservoir blind stadium bore)
        axis = int(np.argmax(m.extents))
        mid = m.bounds[0][axis] + m.extents[axis] * 0.5
        nrm = np.zeros(3)
        nrm[axis] = 1
        sec = m.section(plane_origin=np.where(np.arange(3) == axis, mid, 0), plane_normal=nrm)
        r_bore, sharp = None, 0
        if sec is not None:
            for poly in sec.discrete:
                pts2 = np.delete(poly, axis, axis=1)
                if len(pts2) < 12:
                    continue
                ring = shapely_geom.Polygon(pts2)
                if not ring.is_valid or ring.area < 1:
                    continue
                ccw = ring.exterior.is_ccw
                rr = self.reflex_radii(np.asarray(ring.exterior.coords), ccw)      # radii at concave (cutter-limiting) corners
                big = [r for r in rr if r > 1.0]
                sharp += sum(1 for r in rr if r < 0.5)
                if big:
                    r_bore = min(big) if r_bore is None else min(r_bore, min(big))
        r_min = r_bore
        # cavity depth: ray along the axis from a point inside the bore but off the port axis
        c = m.bounds.mean(axis=0)
        c[axis] = mid
        c[(axis + 1) % 3] += 3.0 if (axis + 1) % 3 == 1 else 0.0
        d = np.zeros(3)
        d[axis] = 1
        depth = None
        ends = []
        for sg in (1, -1):
            loc, ir, _ = m.ray.intersects_location(np.array([c]), np.array([sg * d]), multiple_hits=False)
            ends.append(float(loc[0][axis]) if len(loc) else None)
        if ends[0] is not None and ends[1] is None:        # closed at the +axis end, open at the -axis end: depth = open face to closed wall
            depth = ends[0] - float(m.bounds[0][axis])
        elif ends[1] is not None and ends[0] is None:
            depth = float(m.bounds[1][axis]) - ends[1]
        out["sharp_corners_below_0.5mm"] = sharp
        if sharp:
            out["violations"].append({"sev": "WARN", "what": f"{sharp} sharp inner corner samples (R < 0.5 mm), e.g. the arm slot: needs an end mill no wider than the slot (1.6 mm), not the D5 tool", "where": ""})
        pocket_w = float(np.sort(np.delete(m.extents, axis))[0])
        out["r_min_mm"] = None if r_min is None else round(r_min, 2)
        out["depth_mm"] = None if depth is None else round(depth, 1)
        if r_min is not None and depth:
            r_req = depth / 10 + 0.5
            out["r_required_mm"] = round(r_req, 2)
            if r_min < r_req - 0.1:          # 0.1 mm: tessellation of the R2.5 arc reads about 2.39
                out["violations"].append({"sev": "FAIL", "what": f"internal corner radius {r_min:.2f} mm < {r_req:.2f} mm required for a {depth:.1f} mm deep pocket (R >= H/10 + 0.5, JLCCNC); tool D = {2 * r_min:.1f} mm gives depth/D = {depth / (2 * r_min):.1f}", "where": ""})
            out["depth_over_tool"] = round(depth / (2 * r_min), 1)
            if depth / (2 * r_min) >= cr["tool_depth_special"]:
                out["violations"].append({"sev": "FAIL", "what": f"pocket depth {depth:.1f} mm = {depth / (2 * r_min):.1f} x tool D {2 * r_min:.1f}: needs a special long-reach tool (>= 5 x D)", "where": ""})
            elif depth / (2 * r_min) > cr["tool_depth_best"]:
                out["violations"].append({"sev": "WARN", "what": f"pocket depth/D = {depth / (2 * r_min):.1f} (best 2-3 x D, >= 5 x D special)", "where": ""})
        return out

    @staticmethod
    def reflex_radii(ring: np.ndarray, ccw: bool) -> list[float]:
        ls = LineString(ring)
        n = max(int(ls.length / 0.05), 50)
        pts = np.array([ls.interpolate(i * ls.length / n).coords[0] for i in range(n)])
        k = 6
        out = []
        for i in range(n):
            a, b, c = pts[(i - k) % n], pts[i], pts[(i + k) % n]
            cr = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
            reflex = (cr < 0) if ccw else (cr > 0)
            if not reflex:
                continue
            ab, bc, ca = np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c)
            area2 = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
            out.append(1e3 if area2 < 1e-9 else ab * bc * ca / (2 * area2))
        return out

    @staticmethod
    def min_radius(ring: np.ndarray) -> float:
        ls = LineString(ring)
        n = max(int(ls.length / 0.05), 50)
        pts = np.array([ls.interpolate(i * ls.length / n).coords[0] for i in range(n)])
        k = 6
        best = 1e9
        for i in range(n):
            a, b, c = pts[(i - k) % n], pts[i], pts[(i + k) % n]
            ab, bc, ca = np.linalg.norm(b - a), np.linalg.norm(c - b), np.linalg.norm(a - c)
            area2 = abs((b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0]))
            if area2 < 1e-9:
                continue
            r = ab * bc * ca / (2 * area2)
            best = min(best, r)
        return float(best)

    def run_all(self) -> list[dict]:
        out = []
        for it in self.order_list():
            t0 = time.time()
            r = self.analyse(it)
            print(f"  dfm {r['name']:34} {r.get('verdict', 'ERR'):5} {r.get('process', ''):7} wall_min={r.get('wall_min')} ({time.time() - t0:.0f} s)", flush=True)
            out.append(r)
        return out


# ------------------------------------------------------------------------------------------------------------------------------
# 4. fit classes: nominal gap from the CAD, Monte Carlo with process tolerance
# ------------------------------------------------------------------------------------------------------------------------------
def chord(mesh, normal: str, point, dirn: str, expect: str):
    """Length of the material ('shaft') or void ('hole') interval that contains `point`, measured along axis `dirn`
    in the plane through `point` perpendicular to `normal`.  None if the point is not in such an interval."""
    ai, di = AXI[normal], AXI[dirn]
    sec = mesh.section(plane_origin=np.asarray(point, float), plane_normal=AX[normal])
    if sec is None:
        return None
    keep = [i for i in range(3) if i != ai]
    region = None
    for p in sec.discrete:
        q = p[:, keep]
        if len(q) < 4:
            continue
        poly = shapely_geom.Polygon(q).buffer(0)
        if poly.is_empty:
            continue
        if expect == "outer":                      # filled outline: a bore in the part is ignored
            region = poly if region is None else region.union(poly)
        else:
            region = poly if region is None else region.symmetric_difference(poly)
    if region is None:
        return None
    if expect == "outer":
        expect = "shaft"
    p2 = np.asarray(point, float)[keep]
    d2 = np.zeros(2)
    d2[keep.index(di)] = 1.0
    line = LineString([p2 - d2 * 60, p2 + d2 * 60])
    geom = line.intersection(region) if expect == "shaft" else line.difference(region)
    segs = [geom] if geom.geom_type == "LineString" else list(getattr(geom, "geoms", []))
    best = None
    for s in segs:
        if s.geom_type == "LineString" and s.distance(Point(p2)) < 1e-6:
            best = s.length
    return best


class Fits:
    def __init__(self, M: Model, rules: dict, seq: dict, guide_text: str):
        self.M, self.rules, self.seq, self.guide = M, rules, seq, guide_text
        self.env = Env(M.mech, M.params, M)
        self.env.ns["F"] = lambda p, a, f: M.bb(p, "min", a) + f * (M.bb(p, "max", a) - M.bb(p, "min", a))
        self.env.ns["LAY"] = M.layout

    def sigma(self, spec: str, role: str, scen: dict, scen_name: str) -> tuple[float, float]:
        """(bias, sigma) of a feature of `role` hole/shaft made by `spec` (SLA, MJF, CNC_PP, purchased:key, fixed:tol)."""
        if spec.startswith("purchased:"):
            return 0.0, self.rules["tolerance_scenarios"]["purchased"][spec.split(":")[1]] / 3
        if spec.startswith("fixed:"):
            return 0.0, float(spec.split(":")[1]) / 3
        s = scen[spec]
        k = scen["k_sigma"]
        if role == "hole":
            return s["hole_bias"], s["hole_tol"] / k
        return s["shaft_bias"], s["size_tol"] / k

    def measure(self, side: dict, at) -> float | None:
        if "d" in side:
            return float(side["d"])
        pt = self.env.vec(at)
        return chord(self.M.mesh[side["part"]], side["normal"], pt, side["dir"], side["expect"])

    def window(self, fit: dict, d_hole: float) -> tuple[float, float]:
        fc = self.rules["fit_classes"]
        k = fit["kind"]
        lo, hi = fit.get("window", [None, None])
        if lo is None or hi is None:
            w = fc[k]
            if w.get("hoop"):
                mat = fit.get("material", "SLA_TOUGH")
                lim = self.rules["materials"][mat]["hoop_strain_allow_press"]
                lo_, hi_ = -lim * d_hole, w["gap_max"]
            else:
                lo_, hi_ = w["gap_min"], w["gap_max"]
            lo = lo_ if lo is None else lo
            hi = hi_ if hi is None else hi
        return lo, hi

    def run_fit(self, fit: dict, n: int = 40000) -> dict:
        rec = {"id": fit["id"], "name": fit["name"], "kind": fit["kind"], "step": fit.get("step", ""), "hole_proc": fit["hole_proc"], "shaft_proc": fit.get("shaft_proc", "screw")}
        if fit["kind"] == "pilot":
            return self.run_pilot(fit, rec, n)
        for need in (fit.get("hole", {}).get("part"), fit.get("shaft", {}).get("part")):
            if need and not self.M.has(need):
                rec["status"] = "SKIP"
                rec["note"] = f"body {need} not in this CAD"
                return rec
        at = fit["at"]
        if "gap_expr" in fit:
            gap = self.env.val(fit["gap_expr"])
            dh, ds = None, None
            dh = fit.get("d_nominal", 0) + gap / 2
            ds = dh - gap
        else:
            fit["hole"].setdefault("expect", "hole")
            fit["shaft"].setdefault("expect", "shaft")
            dh = self.measure(fit["hole"], at)
            ds = self.measure(fit["shaft"], fit.get("at_shaft", at))
            if dh is None or ds is None:
                rec["status"] = "NOMEASURE"
                rec["note"] = f"could not measure hole={dh} shaft={ds} at {at}"
                return rec
            if "dh_override" in fit:
                dh = float(fit["dh_override"])
            if "ds_override" in fit:
                ds = float(fit["ds_override"])
        rec["d_hole"], rec["d_shaft"], rec["gap_nominal"] = round(dh, 3), round(ds, 3), round(dh - ds, 3)
        lo, hi = self.window(fit, dh)
        rec["window"] = [round(lo, 3), round(hi, 3)]
        rng = np.random.default_rng(3)
        rec["scenarios"] = {}
        for sn in ("project", "vendor"):
            scen = self.rules["tolerance_scenarios"][sn]
            bh, sh_ = self.sigma(fit["hole_proc"], "hole", scen, sn)
            bs, ss = self.sigma(fit["shaft_proc"], "shaft", scen, sn)
            g = (dh + bh + rng.normal(0, sh_, n)) - (ds + bs + rng.normal(0, ss, n))
            p_tight, p_loose = float(np.mean(g < lo)), float(np.mean(g > hi))
            rec["scenarios"][sn] = {"p_ok": round(1 - p_tight - p_loose, 3), "p_too_tight": round(p_tight, 3), "p_too_loose": round(p_loose, 3),
                                    "gap_mean": round(float(g.mean()), 3), "gap_p01": round(float(np.percentile(g, 1)), 3), "gap_p99": round(float(np.percentile(g, 99)), 3),
                                    "recommended_hole_shift": self.min_shift(g, lo, hi)}
        return self.finish(fit, rec)

    def run_pilot(self, fit: dict, rec: dict, n: int) -> dict:
        w = self.rules["fit_classes"]["pilot"]
        if not self.M.has(fit["hole"]["part"]):
            rec["status"], rec["note"] = "SKIP", "body missing"
            return rec
        pt = self.env.vec(fit["at"])
        vals = []
        for z in fit.get("z_scan", [pt[2]]):
            q = pt.copy()
            q[2] = z
            v = chord(self.M.mesh[fit["hole"]["part"]], "Z", q, "X", "hole")
            if v is not None and v < 5:
                vals.append(v)
        d = float(np.median(vals)) if vals else None
        if d is None:
            rec["status"], rec["note"] = "NOMEASURE", f"no hole found at {pt}"
            return rec
        rec["d_hole"], rec["window"] = round(d, 3), [w["abs_min"], w["abs_max"]]
        rec["gap_nominal"] = None
        rng = np.random.default_rng(5)
        rec["scenarios"] = {}
        for sn in ("project", "vendor"):
            scen = self.rules["tolerance_scenarios"][sn]
            bh, sh_ = self.sigma(fit["hole_proc"], "hole", scen, sn)
            g = d + bh + rng.normal(0, sh_, n)
            pt_, pl_ = float(np.mean(g < w["abs_min"])), float(np.mean(g > w["abs_max"]))
            rec["scenarios"][sn] = {"p_ok": round(1 - pt_ - pl_, 3), "p_too_tight": round(pt_, 3), "p_too_loose": round(pl_, 3), "gap_mean": round(float(g.mean()), 3),
                                    "gap_p01": round(float(np.percentile(g, 1)), 3), "gap_p99": round(float(np.percentile(g, 99)), 3),
                                    "recommended_hole_shift": self.min_shift(g, w["abs_min"], w["abs_max"])}
        return self.finish(fit, rec)

    @staticmethod
    def min_shift(g, lo: float, hi: float):
        """Smallest shift of the hole size that puts the 1 %..99 % range of the gap inside the window; None if the spread is wider than the window."""
        p01, p99 = float(np.percentile(g, 1)), float(np.percentile(g, 99))
        if p99 - p01 > hi - lo:
            return None
        if p01 < lo:
            return round(lo - p01, 3)
        if p99 > hi:
            return round(hi - p99, 3)
        return 0.0

    def finish(self, fit: dict, rec: dict) -> dict:
        th = self.rules["thresholds"]
        pv, pr = rec["scenarios"]["vendor"], rec["scenarios"]["project"]
        worst_p = 1 - pr["p_ok"]
        rec["status"] = "FAIL" if worst_p > th["p_fail_error"] else ("RISK" if worst_p > th["p_fail_warn"] else "OK")
        rec["status_vendor"] = "FAIL" if (1 - pv["p_ok"]) > th["p_fail_error"] else ("RISK" if (1 - pv["p_ok"]) > th["p_fail_warn"] else "OK")
        post = []
        for sn, pp in (("project", pr), ("vendor", pv)):
            if pp["p_too_tight"] > th["p_fail_postprocess"]:
                post.append(f"{sn}: {pp['p_too_tight']*100:.0f} % too tight -> " + fit.get("post_tight", "ream / drill / sand to size"))
            if pp["p_too_loose"] > th["p_fail_postprocess"]:
                post.append(f"{sn}: {pp['p_too_loose']*100:.0f} % too loose -> " + fit.get("post_loose", "adhesive / shim / oversize the mating part"))
        rec["post"] = post
        rx = fit.get("guide_regex")
        if rx:
            rec["in_build_guide"] = bool(re.search(rx, self.guide, re.I | re.S))
            rec["guide_regex"] = rx
        rec["note"] = fit.get("note", "")
        return rec

    def run_all(self) -> list[dict]:
        out = []
        for f in self.seq.get("fits", []):
            if "id" not in f:
                continue
            r = self.run_fit(json.loads(json.dumps(f)))
            out.append(r)
            print(f"  fit {r['id']:5} {r['status']:9} {r['name'][:60]}  gap {r.get('gap_nominal')}", flush=True)
        out += self.dock_snap_mc()
        return out

    # snap arms: Monte Carlo of strain and of 'no latch' for the dock (arm thickness and dome size vary with the process)
    def dock_snap_mc(self) -> list[dict]:
        D, P = self.M.mech["dock"], self.M.params
        cn = P["cannula"]
        res = []
        for mat, proc in (("SLA_TOUGH", "SLA"), ("PA12_MJF", "MJF")):
            r = {"id": f"SNAP-{proc}", "name": f"dock snap arms ({proc}): strain and latch margin", "kind": "snap", "hole_proc": proc, "shaft_proc": "SLA (dummy head)", "step": "D1",
                 "d_hole": None, "d_shaft": None, "gap_nominal": round(D["travel"], 3), "window": [0.3, None], "scenarios": {}}
            lim = self.rules["materials"][mat]["snap_strain_allow"]
            for sn in ("project", "vendor"):
                scen = self.rules["tolerance_scenarios"][sn]
                rng = np.random.default_rng(9)
                n = 40000
                k = scen["k_sigma"]
                t = D["arm_t"] + scen[proc]["shaft_bias"] + rng.normal(0, scen[proc]["size_tol"] / k, n)       # arm thickness
                dome = cn["A_dome_d"] + rng.normal(0, scen["SLA"]["size_tol"] / k, n)                          # dummy head dome (SLA)
                hook = 2 * D["hook_in"] + scen[proc]["hole_bias"] + rng.normal(0, scen[proc]["hole_tol"] / k, n)  # hook gap (a 'hole')
                delta = (dome - hook) / 2                                                                      # arm tip travel per side
                eps = 1.5 * t * np.maximum(delta, 0) / D["flex_len"] ** 2
                p_break = float(np.mean(eps > lim))
                p_nolatch = float(np.mean(delta < 0.05))              # arms never spread: head not retained (rattles / falls out)
                r["scenarios"][sn] = {"p_ok": round(1 - p_break - p_nolatch, 3), "p_too_tight": round(p_break, 3), "p_too_loose": round(p_nolatch, 3),
                                      "gap_mean": round(float(delta.mean()), 3), "gap_p01": round(float(np.percentile(delta, 1)), 3), "gap_p99": round(float(np.percentile(delta, 99)), 3),
                                      "strain_mean_pct": round(float(eps.mean() * 100), 2), "strain_p99_pct": round(float(np.percentile(eps, 99)) * 100, 2), "recommended_hole_shift": None}
            r["limit_pct"] = lim * 100
            r["note"] = "too_tight = arm strain above the material limit (arm overstressed / breaks); too_loose = no spread (dome smaller than hook gap: no retention). Dome A and hook gap are TODO-MEASURE placeholders in params.json."
            self.finish_snap(r)
            res.append(r)
            print(f"  fit {r['id']:9} {r['status']:9} {r['name'][:60]}", flush=True)
        return res

    def finish_snap(self, r: dict) -> None:
        th = self.rules["thresholds"]
        pr, pv = r["scenarios"]["project"], r["scenarios"]["vendor"]
        r["status"] = "FAIL" if (1 - pr["p_ok"]) > th["p_fail_error"] else ("RISK" if (1 - pr["p_ok"]) > th["p_fail_warn"] else "OK")
        r["status_vendor"] = "FAIL" if (1 - pv["p_ok"]) > th["p_fail_error"] else ("RISK" if (1 - pv["p_ok"]) > th["p_fail_warn"] else "OK")
        r["post"] = []
        r["in_build_guide"] = bool(re.search(r"dock.{0,40}(variant|insert).{0,200}(sweep|rattle|snap)", self.guide, re.I | re.S))


# ------------------------------------------------------------------------------------------------------------------------------
# images
# ------------------------------------------------------------------------------------------------------------------------------
def _plt():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


def section_xy(mesh, axis: str, value: float):
    """Closed rings of the mesh section in the plane axis=value, as 2D arrays in the two remaining axes (in X,Y,Z order)."""
    ai = AXI[axis]
    sec = mesh.section(plane_origin=np.where(np.arange(3) == ai, value, 0.0), plane_normal=AX[axis])
    if sec is None:
        return []
    keep = [i for i in range(3) if i != ai]
    return [p[:, keep] for p in sec.discrete]


def draw_section(ax, meshes: list[tuple[trimesh.Trimesh, str, float]], axis: str, value: float, win, keep_axes):
    from matplotlib.patches import Polygon as MPoly
    for m, col, alpha in meshes:
        b = m.bounds
        ai = AXI[axis]
        if b[0][ai] > value or b[1][ai] < value:
            continue
        for ring in section_xy(m, axis, value):
            ax.add_patch(MPoly(ring, closed=True, facecolor=col, edgecolor=col, alpha=alpha, lw=0.6))
    ax.set_xlim(win[0][0], win[0][1])
    ax.set_ylim(win[1][0], win[1][1])
    ax.set_aspect("equal")
    ax.grid(alpha=0.2)


def render_collision(M: Model, rec: dict, bl: dict, out: Path) -> None:
    plt = _plt()
    off = np.array(bl["offset"])
    c = (np.array(bl["bbox"][0]) + np.array(bl["bbox"][1])) / 2
    movers = [M.mesh[p].copy().apply_translation(off) for p in rec["parts"]]
    fixed = M.mesh[bl["body"]]
    others = [M.mesh[n] for n in M.mesh if n not in rec["parts"] and n != bl["body"] and n not in ("bottom", "top") and np.all(M.mesh[n].bounds[0] < c + 8) and np.all(M.mesh[n].bounds[1] > c - 8)]
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.6))
    R = 7.0
    for ax, (axis, (u, v), lab) in zip(axs, (("Z", (0, 1), "top view (section z = %.2f)"), ("Y", (0, 2), "side view (section y = %.2f)"), ("X", (1, 2), "end view (section x = %.2f)"))):
        val = c[AXI[axis]]
        win = ((c[u] - R, c[u] + R), (c[v] - R, c[v] + R))
        draw_section(ax, [(m, "#888888", 0.35) for m in others] + [(fixed, "#3355aa", 0.35)] + [(m, "#cc2222", 0.45) for m in movers], axis, val, win, None)
        ax.plot([bl["bbox"][0][u], bl["bbox"][1][u], bl["bbox"][1][u], bl["bbox"][0][u], bl["bbox"][0][u]], [bl["bbox"][0][v], bl["bbox"][0][v], bl["bbox"][1][v], bl["bbox"][1][v], bl["bbox"][0][v]], "k-", lw=1.2)
        ax.set_title(lab % val, fontsize=9)
        ax.set_xlabel("XYZ"[u] + " [mm]")
        ax.set_ylabel("XYZ"[v] + " [mm]")
    fig.suptitle(f"{rec['id']}: {rec['title']}\nred = moving {', '.join(rec['parts'][:3])} at {bl['at_s']:.2f} mm before the CAD position; blue = {bl['body']}; box = overlap {bl['max_mm3']:.3f} mm3", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def render_dfm(rec: dict, out: Path) -> None:
    plt = _plt()
    pts, th = rec["_pts"], rec["_thick"]
    vendor, floor = rec["wall_vendor"], rec["wall_floor"]
    fig, axs = plt.subplots(1, 3, figsize=(15, 4.4))
    ok = np.isfinite(th)
    for ax, (u, v, lab) in zip(axs, ((0, 1, "top (X-Y)"), (0, 2, "side (X-Z)"), (1, 2, "end (Y-Z)"))):
        ax.scatter(pts[:, u], pts[:, v], s=0.4, c="#cccccc", rasterized=True)
        low = ok & (th < vendor)
        sc = ax.scatter(pts[low, u], pts[low, v], s=2.5, c=th[low], cmap="autumn", vmin=0, vmax=vendor, rasterized=True)
        bad = ok & (th < floor)
        ax.scatter(pts[bad, u], pts[bad, v], s=6, c="k", marker="x", rasterized=True)
        for h in rec["holes"]:
            if h["verdict"] != "OK":
                ax.plot(h["where"][u], h["where"][v], "bo", mfc="none", ms=9)
        ax.set_aspect("equal")
        ax.set_title(lab, fontsize=9)
        ax.grid(alpha=0.2)
    fig.suptitle(f"{rec['name']} ({rec['process']}): wall thickness below the vendor value {vendor:.2f} mm (orange->yellow), below the hard floor {floor} mm (black x), flagged holes (blue circles)", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    plt.close(fig)


def render_fits(fits: list[dict], out: Path) -> None:
    plt = _plt()
    rows = [f for f in fits if f.get("scenarios")]
    fig, ax = plt.subplots(figsize=(10, 0.32 * len(rows) + 1.5))
    y = np.arange(len(rows))
    ax.barh(y + 0.18, [f["scenarios"]["project"]["p_ok"] * 100 for f in rows], 0.35, label="project tolerances (SLA +-0.05, MJF +-0.10)", color="#3a7")
    ax.barh(y - 0.18, [f["scenarios"]["vendor"]["p_ok"] * 100 for f in rows], 0.35, label="vendor guideline (SLA +-0.2, MJF +-0.3)", color="#c63")
    ax.set_yticks(y)
    ax.set_yticklabels([f"{f['id']} {f['name'][:52]}" for f in rows], fontsize=7)
    ax.invert_yaxis()
    ax.set_xlabel("probability the pair lands in its fit window [%] (Monte Carlo, as printed, no post-processing)")
    ax.axvline(95, color="k", lw=0.6, ls=":")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    plt.close(fig)


def render_tool(M: Model, rec: dict, tool_mesh, out: Path, centre) -> None:
    plt = _plt()
    c = np.asarray(centre)
    fig, axs = plt.subplots(1, 2, figsize=(10, 4.6))
    R = 9.0
    near = [M.mesh[n] for n in M.mesh if np.all(M.mesh[n].bounds[0] < c + R) and np.all(M.mesh[n].bounds[1] > c - R)]
    for ax, (axis, (u, v)) in zip(axs, (("Y", (0, 2)), ("X", (1, 2)))):
        win = ((c[u] - R, c[u] + R), (c[v] - 3, c[v] + 2 * R))
        draw_section(ax, [(m, "#888888", 0.4) for m in near] + [(tool_mesh, "#cc2222", 0.45)], axis, c[AXI[axis]], win, None)
        ax.set_title(f"section {axis} = {c[AXI[axis]]:.2f}", fontsize=9)
    fig.suptitle(f"{rec['id']}: {rec.get('title', '')} (red = tool)", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    plt.close(fig)


# ------------------------------------------------------------------------------------------------------------------------------
# report
# ------------------------------------------------------------------------------------------------------------------------------
def classify_block(rec: dict) -> None:
    """Grazing overlaps (thinnest side of the overlap box <= 0.15 mm) are MARGINAL: within the process tolerance of either part."""
    if rec.get("status") != "BLOCKED":
        return
    real = []
    for b in rec["blocked_by"]:
        dims = np.array(b["bbox"][1]) - np.array(b["bbox"][0])
        b["thin_mm"] = round(float(dims.min()), 3)
        b["marginal"] = bool(dims.min() <= 0.15)
        if not b["marginal"]:
            real.append(b)
    if not real:
        rec["status"] = "MARGINAL"


def sym(s: str) -> str:
    return {"OK": "OK", "BLOCKED": "**BLOCKED**", "MARGINAL": "marginal", "FAIL": "**FAIL**", "RISK": "risk", "TIGHT": "tight", "WARN": "warn", "SKIP": "skip", "FINAL-INTERFERENCE": "**CAD INTERFERENCE**", "NOMEASURE": "n/a"}.get(s, s)


def build_report(ctx: dict) -> str:
    L: list[str] = []
    A = L.append
    p, M = ctx["size"], ctx["M"]
    steps, acc, dfm, fits = ctx["steps"], ctx["access"], ctx["dfm"], ctx["fits"]
    props = ctx.get("proposal_results", [])
    A(f"# Assembly-feasibility and DFM report, bench pod {p}")
    A("")
    A("> **TEST PROJECT: NOT A MEDICAL DEVICE. WATER ONLY. Never worn, never filled with insulin or any drug** (see `DISCLAIMER.md`). Generated by `mechanical/check_assembly.py`; do not edit by hand.")
    A("")
    A(f"* CAD: `out/bench/{p}.sc` sha256 `{ctx['sha'][:12]}`, {len(M.mesh)} bodies, meshes {M.quality} quality; sweep step {ctx['step']} mm; run {ctx['date']}")
    A("* Rules: `dfm_rules.json` (vendor numbers with sources and retrieval date), sequence: `assembly_sequence.json`")
    A("* Overlap criterion: boolean-intersection volume > 1e-4 mm3 (as `check.py`); a grazing overlap (thinnest side <= 0.15 mm) is reported as *marginal*")
    A("")
    # ---- summary
    n_blocked = sum(1 for s in steps if s["status"] in ("BLOCKED", "FINAL-INTERFERENCE"))
    n_marg = sum(1 for s in steps if s["status"] == "MARGINAL")
    n_acc_bad = sum(1 for a in acc if a["status"] in ("BLOCKED",))
    n_acc_tight = sum(1 for a in acc if a["status"] == "TIGHT")
    dfm_fail = [d for d in dfm if d.get("verdict") == "FAIL"]
    fit_fail = [f for f in fits if f["status"] == "FAIL"]
    fit_risk = [f for f in fits if f["status"] == "RISK"]
    A("## 1. Summary (the honest answer)")
    A("")
    A(f"**Can the parts be assembled? Not as the CAD and the build guide stand.** The final assembled state is clean (`check.py`), but replaying the documented order with real insertion paths gives "
      f"**{n_blocked} blocked step(s)** of {len(steps)} ({n_marg} more are grazing/marginal), **{n_acc_bad} tool-access failure(s)** ({n_acc_tight} tight), "
      f"**{len(dfm_fail)} of {len(dfm)} order files with a feature below the process hard floor**, and **{len(fit_fail)} fit(s) that fail and {len(fit_risk)} at risk** as printed (Monte Carlo, project tolerances).")
    A("")
    A("| area | result |")
    A("|---|---|")
    for s in steps:
        if s["status"] in ("BLOCKED", "FINAL-INTERFERENCE"):
            first = s["blocked_by"][0]
            A(f"| step {s['id']} {s['title'][:70]} | **BLOCKED** by `{first['body']}` at {first['first_s']:.2f} mm before the CAD position |")
    for a in acc:
        if a["status"] == "BLOCKED":
            A(f"| access {a['id']} | **BLOCKED** {a.get('title', '')[:60]} ({', '.join((a.get('blockers') or a.get('blockers_lever') or {}).keys())}) |")
    for d in dfm_fail:
        fl = [v for v in d["violations"] if v["sev"] == "FAIL"]
        A(f"| DFM {d['name']} ({d['process']}) | **{len(fl)} distinct FAIL**, worst: " + "; ".join(v["what"][:80] for v in fl[:2]) + " |")
    for f in fit_fail:
        A(f"| fit {f['id']} {f['name'][:50]} | **FAIL** project: {f['scenarios']['project']['p_ok'] * 100:.0f} % in window; vendor: {f['scenarios']['vendor']['p_ok'] * 100:.0f} % |")
    A("")
    A("What was **not** checked (limits of this tool): flexible parts (motor lead wires, FFC cable bending, silicone seals) are rigid meshes or absent; no friction/force model (press-in forces); "
      "purchased parts are the CAD stand-ins (motor, gears are tip-circle cylinders, thread not modelled); the lid-screw head is not a body; vendor numbers are a snapshot of their web pages.")
    A("")
    # ---- sequence
    A("## 2. Assembly sequence: insertion paths")
    A("")
    A("Each part moves from outside to its CAD position along the path in `assembly_sequence.json` (increment " + str(ctx["step"]) + " mm); `s` = distance still to travel. "
      "Engagement overlaps with the intended mating part (press zone / snap arms / stretched rings) are tolerated and listed under *events*.")
    A("")
    A("| step | what (build guide) | tool | status | first collision / notes |")
    A("|---|---|---|---|---|")
    for s in steps:
        note = ""
        if s["status"] in ("BLOCKED", "FINAL-INTERFERENCE", "MARGINAL"):
            bs = s.get("blocked_by", [])
            note = "; ".join(f"`{b['body']}` {b['first_s']:.2f}->{b['last_s']:.2f} mm, max {b['max_mm3']:.3f} mm3 at x {b['bbox'][0][0]}..{b['bbox'][1][0]}, y {b['bbox'][0][1]}..{b['bbox'][1][1]}, z {b['bbox'][0][2]}..{b['bbox'][1][2]}" + (" (grazing)" if b.get("marginal") else "") for b in bs[:3])
        if s.get("alternatives"):
            note += "<br>feasible alternative path: **" + s["alternatives"][0]["path"] + "**"
        elif s["status"] == "BLOCKED":
            note += "<br>no feasible straight or lift-and-slide path found"
        for ev in s["events"]:
            if ev["kind"] == "snap":
                note += (f"<br>snap: deflection {ev['required_deflection_mm']} mm, arm strain {ev['strain_pct']} % vs {ev['limit_pct']:.0f} % ({ev['material']}); CAD travel {ev['cad_travel_mm']} mm = {ev['cad_strain_pct']} %")
            elif ev["kind"] == "flexible":
                note += f"<br>flexible part crosses the path (overlap {ev['max_overlap_mm3']} mm3): must be threaded/lifted by hand"
            elif ev["kind"] == "press":
                note += f"<br>press zone {ev['pair'][1]}: overlap {ev['max_overlap_mm3']} mm3 over the last {ev['from_s']:.2f} mm"
            elif ev["kind"] == "stretch":
                note += f"<br>elastic ring stretch over {ev['pair'][1]} (overlap {ev['max_overlap_mm3']} mm3)"
        img = s.get("image")
        if img:
            note += f"<br>![{s['id']}]({img})"
        A(f"| {s['id']} | {s['title']} ({s['guide']}) | {s['tool']} | {sym(s['status'])} | {note} |")
    A("")
    unassigned = ctx["unassigned"]
    if unassigned:
        A(f"CAD bodies not part of any step in `assembly_sequence.json`: {', '.join(unassigned)} (add them or the sequence is out of date).")
        A("")
    # proposals
    if props:
        A("### 2a. Proposed re-ordering tested with the same engine")
        A("")
        for pr in props:
            A(f"**{pr['id']}: {pr['title']}**")
            A("")
            A("| step | status | notes |")
            A("|---|---|---|")
            for s in pr["steps"]:
                note = ""
                if s["status"] in ("BLOCKED", "FINAL-INTERFERENCE", "MARGINAL"):
                    note = "; ".join(f"`{b['body']}` {b['first_s']:.2f} mm, {b['max_mm3']:.3f} mm3" for b in s.get("blocked_by", [])[:2])
                if s.get("alternatives"):
                    note += " (alt: " + s["alternatives"][0]["path"] + ")"
                A(f"| {s['id']} {s['title'][:80]} | {sym(s['status'])} | {note} |")
            A("")
    # ---- access
    A("## 3. Tool and finger access")
    A("")
    T = ctx["seq"]["tools"]
    A(f"Screwdriver model: tip D1.5 / D2.0 x {T['driver']['tip_len']} mm, shaft D{T['driver']['shaft_d']} up to {T['driver']['shaft_len']} mm above the head, handle D{T['driver']['handle_d']} beyond; must stay free when tilted {ctx['rules']['thresholds']['min_free_tilt_driver_deg']} deg in 8 directions. "
      f"Tweezers: cone half angle {T['tweezers']['cone_half_angle_deg']} deg, tip D{T['tweezers']['tip_d']}, length {T['tweezers']['length']} mm, apex on the trailing face of the part, approach opposite the insertion direction, tilted up to {T['tweezers']['max_tilt_deg']} deg allowed. ZIF: lever swing box above the connector rear edge + tweezer approach.")
    A("")
    A("| item | status | detail |")
    A("|---|---|---|")
    for a in acc:
        if a["kind"] == "driver":
            det = (f"seat z {a.get('seat_z')}, free tilt tip1.5 {a['tip_1.5']['free_tilt_deg']} deg / tip2.0 {a['tip_2.0']['free_tilt_deg']} deg (need {a['required_tilt_deg']}), "
                   f"min tip length that clears: {a['min_tip_len_mm']} mm; blockers: {', '.join(list(a['tip_1.5']['blockers'].keys()) + list(a['tip_2.0']['blockers'].keys())) or '-'}")
        elif a["kind"] == "tweezers":
            det = f"free cone half angle {a['max_free_half_angle_deg']} deg (need {a['required_deg']}); blockers: {', '.join(a['blockers'].keys()) or '-'}"
        else:
            det = f"lever box blockers: {', '.join(a.get('blockers_lever', {}).keys()) or '-'}; free tweezer approach {a.get('free_approach_deg')} deg"
        img = a.get("image")
        A(f"| {a['id']} {a.get('title', '')[:60]} | {sym(a['status'])} | {det}" + (f"<br>![{a['id']}]({img})" if img else "") + " |")
    A("")
    # ---- DFM
    A("## 4. DFM against the vendor rules")
    A("")
    A("Wall thickness = inward ray from 60 000 surface samples to the first opposite surface (vendor table value interpolated by part footprint; hard floor = below this the feature is not reliably producible). "
      "Void width = outward ray; round holes/channels are separated from slots by sampling the cross-section; depth along the axis. CNC: section ring curvature and axial depth.")
    A("")
    A("| part | process | extents [mm] | min wall | % wall < vendor | vendor / floor | flagged voids | verdict |")
    A("|---|---|---|---|---|---|---|---|")
    for d in dfm:
        if "error" in d:
            A(f"| {d['name']} | | | | | | | error |")
            continue
        nv = sum(1 for h in d["holes"] if h["verdict"] != "OK")
        A(f"| {d['name']} | {d['process']} | {' x '.join(str(x) for x in d['extents'])} | {d['wall_min']:.2f} | {d['area_below_vendor_pct']} | {d['wall_vendor']:.2f} / {d['wall_floor']} | {nv} | {sym(d['verdict'])} |")
    A("")
    A("### 4a. Violations with location (pod coordinates of the mesh)")
    A("")
    for d in dfm:
        if "error" in d or not d["violations"]:
            continue
        A(f"**{d['name']}** ({d['process']}, qty {d['qty']})")
        A("")
        for v in d["violations"]:
            A(f"* {v['sev']}: {v['what']}" + (f" at {v['where']}" if v["where"] else "") + (f" and {v['places'] - 1} more place(s), e.g. {v['also'][0]}" if v.get("places", 1) > 1 and v["also"] and v["also"][0] else "") + (f" ({v['n']} samples)" if v.get("n") else ""))
        if d.get("image"):
            A("")
            A(f"![{d['name']}]({d['image']})")
        A("")
    A("### 4b. Parts that cannot be made as drawn")
    A("")
    cant = []
    for d in dfm:
        for v in d.get("violations", []):
            if v["sev"] == "FAIL":
                cant.append((d["name"], d["process"], v["what"], v["where"]))
    if cant:
        for n, pr_, w, loc in cant:
            A(f"* `{n}` ({pr_}): {w}" + (f" at {loc}" if loc else ""))
    else:
        A("None.")
    A("")
    # ---- fits
    A("## 5. Fit classes and process tolerance")
    A("")
    A("Gap g = hole - shaft measured on the CAD meshes (negative = interference). Monte Carlo (40 000 draws): hole = nominal + bias + N(0, tol/k), shaft = nominal + N(0, tol/k); "
      "'project' = tolerances the CAD/sim assume, 'vendor' = tolerances the vendor guide quotes. The window is the range of g where the pair works as intended (class defaults in `dfm_rules.json`). "
      "Post-processing = what has to be done to the part when the as-printed probability is poor; the last column says whether the build guide mentions it.")
    A("")
    A(f"![fits](img/{p}_fits.png)")
    A("")
    A("| id | pair | class | g nominal | window | project: ok / tight / loose | vendor: ok / tight / loose | status | post-processing needed | in guide |")
    A("|---|---|---|---|---|---|---|---|---|---|")
    for f in fits:
        if f["status"] in ("SKIP", "NOMEASURE"):
            A(f"| {f['id']} | {f['name']} | {f['kind']} | | | | | {f['status']} | {f.get('note', '')} | |")
            continue
        sp, sv = f["scenarios"]["project"], f["scenarios"]["vendor"]
        gap = f["gap_nominal"] if f.get("gap_nominal") is not None else f"d {f['d_hole']}"
        win = f["window"]
        post = "<br>".join(f["post"]) if f["post"] else "-"
        gd = {True: "yes", False: "**NO**", None: "-"}[f.get("in_build_guide")] if f["post"] else "-"
        A(f"| {f['id']} | {f['name']} | {f['kind']} | {gap} | {win[0]}..{win[1]} | {sp['p_ok'] * 100:.0f} / {sp['p_too_tight'] * 100:.0f} / {sp['p_too_loose'] * 100:.0f} % | {sv['p_ok'] * 100:.0f} / {sv['p_too_tight'] * 100:.0f} / {sv['p_too_loose'] * 100:.0f} % | {sym(f['status'])} (vendor: {sym(f['status_vendor'])}) | {post} | {gd} |")
    A("")
    snaps = [f for f in fits if f["kind"] == "snap"]
    for f in snaps:
        sp, sv = f["scenarios"]["project"], f["scenarios"]["vendor"]
        A(f"* {f['name']}: strain mean/p99 project {sp['strain_mean_pct']}/{sp['strain_p99_pct']} %, vendor {sv['strain_mean_pct']}/{sv['strain_p99_pct']} % vs limit {f['limit_pct']:.0f} %.")
    A("")
    # ---- proposals text
    A("## 6. Fix proposals for the CAD owner (nothing was changed in the CAD)")
    A("")
    for t in ctx["fix_text"]:
        A(t)
    A("")
    return "\n".join(L) + "\n"


# ------------------------------------------------------------------------------------------------------------------------------
# orchestration
# ------------------------------------------------------------------------------------------------------------------------------
def man_to_tri(m):
    mm = m.to_mesh()
    return trimesh.Trimesh(np.asarray(mm.vert_properties)[:, :3], np.asarray(mm.tri_verts), process=False)


def run_proposals(M: Model, seq: dict, rules: dict, step: float) -> list[dict]:
    """Re-run the sequence with the re-ordering / replaced steps of seq['proposals']; only steps from the first change on are swept."""
    out = []
    docs = {s["id"]: s for s in seq["steps"]}
    for pr in seq.get("proposals", []):
        S = Sequencer(M, seq, rules, step)
        allsteps = dict(docs)
        for ns in pr.get("new_steps", []):
            allsteps[ns["id"]] = ns
        order = pr["order"]
        first_change = next(i for i, sid in enumerate(order) if sid not in docs or i >= len(seq["steps"]) or seq["steps"][i]["id"] != sid)
        res = []
        for i, sid in enumerate(order):
            st = allsteps[sid]
            if i < first_change:
                S.ctx_parts[st["context"]] += [m for m in S.expand(st["parts"]) if m not in S.ctx_parts[st["context"]]]
                continue
            r = S.run_step(st, alt_search=True)
            classify_block(r)
            print(f"  [{pr['id']}] {r['id']:5} {r['status']:10} {r['title'][:70]}", flush=True)
            res.append(r)
        out.append({"id": pr["id"], "title": pr["title"], "steps": res})
    return out


def sha_of(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def check_size(outdir: Path, size: str, args, primary: bool) -> dict:
    root = HERE.parent
    rules, seq = jload(RULES_FILE), jload(seq_path(outdir))
    M = Model(outdir, size, quality=args.quality, refresh=args.refresh)
    only = args.only
    guide = "\n".join(p.read_text() for p in sorted((root / "docs" / "build-guide").glob("*.md"))) if (root / "docs" / "build-guide").exists() else ""
    if is_v010(outdir):      # v0.1.0: post-processing must be documented in mechanical/ASSEMBLY.md (v010 build order)
        guide = (HERE / "ASSEMBLY.md").read_text()
    img = outdir / "assembly-check" / "img"
    img.mkdir(parents=True, exist_ok=True)
    ctx = {"size": size, "M": M, "seq": seq, "rules": rules, "sha": sha_of(M.sc), "step": args.step, "date": time.strftime("%Y-%m-%d"),
           "steps": [], "access": [], "dfm": [], "fits": [], "unassigned": [], "proposal_results": [], "fix_text": []}
    S = Sequencer(M, seq, rules, args.step)
    if only in (None, "paths", "access"):
        print(f"[{size}] 1. assembly paths", flush=True)
        ctx["steps"] = S.run_all()
        for r in ctx["steps"]:
            classify_block(r)
            if r["status"] in ("BLOCKED", "FINAL-INTERFERENCE", "MARGINAL") and r.get("blocked_by"):
                bl = r["blocked_by"][0]
                if r["status"] == "BLOCKED":
                    bl = next((b for b in r["blocked_by"] if not b.get("marginal")), bl)
                try:
                    f = img / f"{size}_step_{r['id']}.png"
                    render_collision(M, r, bl, f)
                    r["image"] = f"img/{f.name}"
                except Exception as ex:      # noqa: BLE001
                    print(f"    image failed: {ex}")
        used = {p for r in ctx["steps"] for p in r["parts"]} | {b for c in seq["contexts"].values() for b in c["base"]}
        ctx["unassigned"] = [b for b in M.mesh if b not in used]
        if seq.get("proposals"):
            print(f"[{size}] 1b. proposed re-ordering", flush=True)
            ctx["proposal_results"] = run_proposals(M, seq, rules, args.step)
    if only in (None, "access"):
        print(f"[{size}] 2. tool and finger access", flush=True)
        if not ctx["steps"]:
            ctx["steps"] = S.run_all()
        ctx["access"] = Access(S).run_all(ctx["steps"])
        for a in ctx["access"]:
            if a["status"] in ("BLOCKED", "TIGHT") and "_tool" in a:
                f = img / f"{size}_access_{a['id']}.png"
                try:
                    render_tool(M, a, a["_tool"], f, a["_centre"])
                    a["image"] = f"img/{f.name}"
                except Exception as ex:      # noqa: BLE001
                    print(f"    image failed: {ex}")
    if only in (None, "dfm") and primary:
        print(f"[{size}] 3. DFM", flush=True)
        D = DFM(M, rules, outdir, size, n_samples=args.samples)
        ctx["dfm"] = D.run_all()
        for d in ctx["dfm"]:
            if d.get("violations") and "_pts" in d:
                f = img / f"dfm_{d['name']}.png"
                try:
                    render_dfm(d, f)
                    d["image"] = f"img/{f.name}"
                except Exception as ex:      # noqa: BLE001
                    print(f"    image failed: {ex}")
    if only in (None, "fits"):
        print(f"[{size}] 4. fit classes", flush=True)
        ctx["fits"] = Fits(M, rules, seq, guide).run_all()
        try:
            render_fits(ctx["fits"], img / f"{size}_fits.png")
        except Exception as ex:      # noqa: BLE001
            print(f"    image failed: {ex}")
    return ctx


def ctx_from_results(outdir: Path, size: str, args) -> dict:
    rules, seq = jload(RULES_FILE), jload(seq_path(outdir))
    M = Model(outdir, size, quality=args.quality)
    r = jload(outdir / "assembly-check" / f"results-{size}.json")
    used = {p for s_ in r["steps"] for p in s_["parts"]} | {b for c in seq["contexts"].values() for b in c["base"]}
    return {"size": size, "M": M, "seq": seq, "rules": rules, "sha": sha_of(M.sc), "step": args.step, "date": time.strftime("%Y-%m-%d"), "steps": r["steps"], "access": r["access"],
            "dfm": r["dfm"], "fits": r["fits"], "unassigned": [b for b in M.mesh if b not in used], "proposal_results": r["proposals"], "fix_text": []}


def fix_texts(ctx: dict) -> list[str]:
    """Fix proposals: step-specific hints from the sequence file (authored from the findings) + rule-derived ones."""
    seq = ctx["seq"]
    out = []
    hints = seq.get("fix_hints", {})
    blocked = [s for s in ctx["steps"] if s["status"] in ("BLOCKED", "FINAL-INTERFERENCE", "MARGINAL")]
    for s in blocked:
        h = hints.get(s["id"])
        if h:
            out.append(f"* **{s['id']} ({s['title'][:60]}):** {h}")
    for a in ctx["access"]:
        if a["status"] in ("BLOCKED", "TIGHT"):
            h = hints.get("access:" + a["id"])
            if h:
                out.append(f"* **access {a['id']}:** {h}")
    for f in ctx["fits"]:
        if f["status"] in ("FAIL", "RISK") and f.get("scenarios") and f["scenarios"]["project"].get("recommended_hole_shift") is not None:
            sh = f["scenarios"]["project"]["recommended_hole_shift"]
            if abs(sh) >= 0.02:
                out.append(f"* **fit {f['id']} ({f['name'][:55]}):** shift the hole by {sh:+.2f} mm in the CAD to bring 98 % of the project-tolerance spread into the window" + (f"; {f['post'][0]}" if f["post"] else ""))
        elif f["status"] in ("FAIL", "RISK") and f.get("scenarios") and f["scenarios"]["project"].get("recommended_hole_shift") is None:
            out.append(f"* **fit {f['id']} ({f['name'][:55]}):** the process spread alone is wider than the window: no nominal works as printed; " + (f["post"][0] if f["post"] else "needs a finishing step"))
    out += ["* " + t for t in seq.get("fix_general", [])]
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir")
    ap.add_argument("--sizes", nargs="*")
    ap.add_argument("--only", choices=["paths", "access", "dfm", "fits"])
    ap.add_argument("--step", type=float, default=0.1, help="insertion sweep increment in mm")
    ap.add_argument("--quality", default="standard", choices=["standard", "fine", "finest"], help="mesh quality of the exported bodies")
    ap.add_argument("--samples", type=int, default=60000, help="surface samples per part for the ray-casting DFM measurements")
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--report-only", action="store_true", help="rebuild REPORT.md from the saved results-<size>.json (after editing hints / wording in assembly_sequence.json)")
    args = ap.parse_args()
    outdir = Path(args.outdir) if args.outdir else HERE / "out" / "bench"
    sizes = args.sizes or ["OP-100"]
    rc = 0
    for k, size in enumerate(sizes):
        if args.report_only:
            ctx = ctx_from_results(outdir, size, args)
        else:
            ctx = check_size(outdir, size, args, primary=(k == 0))
        ctx["fix_text"] = fix_texts(ctx)
        rep = build_report(ctx)
        name = "REPORT.md" if k == 0 else f"REPORT-{size}.md"
        d = outdir / "assembly-check"
        if args.only is None:
            (d / name).write_text(rep)
            if args.report_only:
                print(f"rewrote {d / name}")
                continue
            slim = {"size": size, "steps": ctx["steps"], "access": [{k_: v for k_, v in a.items() if not k_.startswith("_")} for a in ctx["access"]],
                    "dfm": [{k_: v for k_, v in x.items() if not k_.startswith("_")} for x in ctx["dfm"]], "fits": ctx["fits"], "proposals": ctx["proposal_results"]}
            (d / f"results-{size}.json").write_text(json.dumps(slim, indent=1, default=str))
            print(f"wrote {d / name}")
        bad = [f"step {s['id']} blocked" for s in ctx["steps"] if s["status"] in ("BLOCKED", "FINAL-INTERFERENCE")]
        bad += [f"access {a['id']} blocked" for a in ctx["access"] if a["status"] == "BLOCKED"]
        bad += [f"DFM {x['name']}: part cannot be made as drawn" for x in ctx["dfm"] if x.get("verdict") == "FAIL"]
        v10 = is_v010(outdir)
        bad += [f"fit {f['id']} fails and the build guide does not cover the post-processing" for f in ctx["fits"]
                if (f["status"] == "FAIL" or (v10 and f.get("status_vendor") == "FAIL")) and f.get("in_build_guide") is not True]
        print(f"\n[{size}] {len(bad)} blocking finding(s)")
        for b in bad:
            print("   FAIL:", b)
        rc |= 1 if bad else 0
    sys.exit(rc)


def run_from_check(outdir: Path, sizes: list[str] | None = None, step: float = 0.1) -> int:
    """Entry for check.py --assembly."""
    sys.argv = ["check_assembly.py", "--outdir", str(outdir), "--step", str(step)] + (["--sizes"] + sizes if sizes else [])
    try:
        main()
    except SystemExit as e:
        return int(e.code or 0)
    return 0


if __name__ == "__main__":
    main()
