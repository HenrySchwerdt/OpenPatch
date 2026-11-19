"""Plunger seal model: line load of a cast silicone bead / lip from a plane-strain finite-element cross-section,
friction from it, eccentric-push (cocking) amplification, leak margin.

Used by a1_drive.py (force budget, Monte Carlo) and a6_seal.py (variant study).  Test project, bench use only
(WATER ONLY), never on a person.

Model chain (every input tagged [LIT] / [ASM] / [CAD] in common.CONST or params.json -> seal):

1. Gent (1958): Young's modulus E from Shore A.  Silicone is nearly incompressible (nu ~ 0.49).
2. Cross-section of the cast ring in its groove (x axial, r radial): bonded/clamped at the groove floor, axially confined by the groove
   walls (frictionless), top surface of the bead pushed down by the net interference delta onto the (rigid) bore wall.  Linear-elastic plane
   strain Q4 elements, B-bar (mean-dilatation) formulation against volumetric locking, active-set contact on the bead top.  Result:
   line load F' [N/mm of seal length] and contact width b [mm] per unit of E and delta; linear in E, close to linear in delta
   for delta/t <= 15 % (check: the Hertz line-contact limit F' = (pi/2) E* delta is the thick-ring upper bound).
3. Normal force N = F' x perimeter x beads; kinetic friction F = mu_k N; breakaway = k_b F (dwell, adhesion).
4. Cocking: the carriage tongue pushes at y = +e from the plunger axis, so the core is pressed against the bore walls with a couple;
   F_push = F_seal / (1 - 2 mu_g e / L_g)  (L_g = distance of the two guide contacts, mu_g = guide band vs PP; jams at 2 mu_g e / L_g >= 1).
5. Leak margin: mean contact pressure p_c = F'/b (lower bound for the pressure under the land, peak ~1.3-1.5x) against 30 kPa (occlusion)
   and 40 kPa (draw suction).
"""
from __future__ import annotations

import math

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

PI = math.pi


def gent_E(shore: float) -> float:
    """Young's modulus [MPa] from Shore A (Gent 1958)."""
    return 0.0981 * (56 + 7.62336 * shore) / (0.137505 * (254 - 2.54 * shore))


def perim_stadium(w: float, h: float) -> float:
    return 2.0 * (w - h) + PI * h


# ----------------------------------------------------------------------------------------------------------
# Plane-strain FE of the ring cross-section
# ----------------------------------------------------------------------------------------------------------
def _gauss():
    g = 1 / math.sqrt(3)
    return [(-g, -g), (g, -g), (g, g), (-g, g)]


def _q4_ke(xy, D, Dvol):
    """Element stiffness, 2x2 Gauss for the deviatoric part, B-bar (mean volumetric strain) for the volumetric part."""
    ke = np.zeros((8, 8))
    # volumetric B-bar: average of (dN/dx, dN/dy) over the element
    Bv = np.zeros((1, 8))
    area = 0.0
    for xi, eta in _gauss():
        dN = 0.25 * np.array([[-(1 - eta), (1 - eta), (1 + eta), -(1 + eta)], [-(1 - xi), -(1 + xi), (1 + xi), (1 - xi)]])
        J = dN @ xy
        dJ = np.linalg.det(J)
        dNxy = np.linalg.solve(J, dN)
        for i in range(4):
            Bv[0, 2 * i] += dNxy[0, i] * dJ
            Bv[0, 2 * i + 1] += dNxy[1, i] * dJ
        area += dJ
    Bv /= area
    for xi, eta in _gauss():
        dN = 0.25 * np.array([[-(1 - eta), (1 - eta), (1 + eta), -(1 + eta)], [-(1 - xi), -(1 + xi), (1 + xi), (1 - xi)]])
        J = dN @ xy
        dJ = np.linalg.det(J)
        dNxy = np.linalg.solve(J, dN)
        B = np.zeros((3, 8))
        for i in range(4):
            B[0, 2 * i] = dNxy[0, i]
            B[1, 2 * i + 1] = dNxy[1, i]
            B[2, 2 * i] = dNxy[1, i]
            B[2, 2 * i + 1] = dNxy[0, i]
        # remove the pointwise volumetric part, add the averaged one
        m = np.array([[1.0], [1.0], [0.0]])
        Bd = B - 0.5 * m @ np.array([[1, 1, 0]]) @ B
        Bb = Bd + 0.5 * m @ Bv
        ke += Bb.T @ D @ Bb * dJ
    return ke


def ring_fe(profile, E=1.5, nu=0.49, h=0.025, floor_bonded=True, tip_clip=None):
    """Line load of one ring in its groove.

    profile: dict(width=groove width [mm], r_base=radial height of the groove floor -> core OD [mm],
                  r_bore=radial height of the bore wall above the floor [mm] (= groove depth + core clearance),
                  delta=net interference per side [mm], pts=[(x, r_top)...] polyline of the free top surface, x 0..width)
    returns dict(Fp [N/mm], b_contact [mm], p_mean [MPa], p_max [MPa], n_contact).
    Units: mm, MPa -> N/mm.
    """
    xs_p = np.array([p[0] for p in profile["pts"]])
    rs_p = np.array([p[1] for p in profile["pts"]])
    W = profile["width"]
    delta = profile["delta"]
    r_bore_free = profile["r_bore"] + delta           # free tip height above the floor (before pushing it into the bore)
    nx = int(round(W / h))
    nr = int(math.ceil(rs_p.max() / h))
    X = np.linspace(0, W, nx + 1)
    R = np.linspace(0, rs_p.max(), nr + 1)
    topx = lambda x: np.interp(x, xs_p, rs_p)
    # node grid, snap the top row of each column to the profile (vertical stretch)
    node_id = -np.ones((nx + 1, nr + 1), int)
    coords = []
    for i, x in enumerate(X):
        ht = float(topx(x))
        m = max(int(round(ht / h)), 1)
        for j in range(m + 1):
            node_id[i, j] = len(coords)
            coords.append((x, ht * j / m))
    coords = np.array(coords)
    elems = []
    for i in range(nx):
        for j in range(nr):
            n = [node_id[i, j], node_id[i + 1, j], node_id[i + 1, j + 1], node_id[i, j + 1]]
            if min(n) >= 0:
                elems.append(n)
    elems = np.array(elems)
    ndof = 2 * len(coords)
    D = E / ((1 + nu) * (1 - 2 * nu)) * np.array([[1 - nu, nu, 0], [nu, 1 - nu, 0], [0, 0, (1 - 2 * nu) / 2]])
    rows, cols, vals = [], [], []
    for e in elems:
        ke = _q4_ke(coords[e], D, None)
        dofs = np.array([[2 * n, 2 * n + 1] for n in e]).ravel()
        rows.extend(np.repeat(dofs, 8))
        cols.extend(np.tile(dofs, 8))
        vals.extend(ke.ravel())
    K = sp.csr_matrix((vals, (rows, cols)), shape=(ndof, ndof))
    fixed = {}
    for n, (x, r) in enumerate(coords):
        if r < 1e-9:
            fixed[2 * n + 1] = 0.0
            if floor_bonded:
                fixed[2 * n] = 0.0
        if (x < 1e-9 or x > W - 1e-9) and r <= profile['r_base'] + 1e-9:      # groove walls only up to the core OD
            fixed[2 * n] = 0.0
    top = [n for n, (x, r) in enumerate(coords) if r > profile["r_bore"] + 1e-9 and abs(r - float(topx(x))) < 1e-9]
    # active set contact: node touches the bore wall if its free height exceeds r_bore
    active = {n for n in top if coords[n][1] > profile["r_bore"] + 1e-9}
    for it in range(30):
        fx = dict(fixed)
        for n in active:
            fx[2 * n + 1] = profile["r_bore"] - coords[n][1]
        fd = np.array(sorted(fx))
        free = np.setdiff1d(np.arange(ndof), fd)
        u = np.zeros(ndof)
        u[fd] = [fx[k] for k in fd]
        rhs = -K[free][:, fd] @ u[fd]
        u[free] = spla.spsolve(K[free][:, free].tocsc(), rhs)
        f = K @ u
        react = {n: f[2 * n + 1] for n in active}
        # release nodes in tension (reaction pulling), add penetrating ones
        # f = K u is the external nodal force that holds the node on the wall: the wall pushes the ring DOWN (f_r < 0) in compression
        rel = {n for n, v in react.items() if v > 0}
        add = {n for n in top if n not in active and coords[n][1] + u[2 * n + 1] > profile["r_bore"] + 1e-9}
        if not rel and not add:
            break
        active = (active - rel) | add
    Fn = {n: -f[2 * n + 1] for n in active}
    Fp = float(sum(max(v, 0) for v in Fn.values()))
    xs_c = np.array([coords[n][0] for n in active])
    b = float(xs_c.max() - xs_c.min()) if len(xs_c) > 1 else 0.0
    p = [Fn[n] / h for n in active]
    return {"Fp": Fp, "b": b, "p_mean": Fp / b if b > 0 else 0.0, "p_max": max(p) if p else 0.0, "n_contact": len(active)}


# ----------------------------------------------------------------------------------------------------------
# Ring cross-section profiles
# ----------------------------------------------------------------------------------------------------------
def v_bead_profile(groove_w, gd, clr, delta, land, flank):
    """Trapezoid bead: base at the core OD (r = gd), flank width `flank` each side, flat land `land`, tip at the bore wall + delta."""
    r_bore = gd + clr
    r_tip = r_bore + delta
    x0 = (groove_w - land) / 2 - flank
    pts = [(0.0, gd)]
    if x0 > 0:
        pts.append((x0, gd))
    pts += [(x0 + flank if x0 > 0 else (groove_w - land) / 2, r_tip), (groove_w - (x0 + flank if x0 > 0 else (groove_w - land) / 2), r_tip)]
    if x0 > 0:
        pts.append((groove_w - x0, gd))
    pts.append((groove_w, gd))
    return {"width": groove_w, "r_base": gd, "r_bore": r_bore, "delta": delta, "pts": pts}


def flat_band_profile(groove_w, gd, clr, delta):
    """Existing design: full-width band (flat top at bore + delta)."""
    r_bore = gd + clr
    return {"width": groove_w, "r_base": gd, "r_bore": r_bore, "delta": delta, "pts": [(0.0, r_bore + delta), (groove_w, r_bore + delta)]}


def line_load_per_E(profile, nu=0.49, h=0.025, floor_bonded=True):
    """F' / E [mm] and contact width for a profile (E = 1 MPa)."""
    r = ring_fe(profile, E=1.0, nu=nu, h=h, floor_bonded=floor_bonded)
    return r


def hertz_line(E, delta, nu=0.49):
    """Thick-ring upper bound: elastic cylinder on a flat, F' = (pi/2) E* delta (small strain), E* = E/(1-nu^2)."""
    return PI / 2 * E / (1 - nu * nu) * delta


def cup_lip(E, t, L, delta, P_kPa):
    """Pressure-energised cantilever skirt (cup lip): preload from bending + fluid pressure on the back of the lip.  F' [N/mm]."""
    pre = E * t ** 3 * delta / (4 * L ** 3)
    return pre + P_kPa * 1e-3 * L


def cocking_factor(mu_g, e, Lg):
    d = 1.0 - 2.0 * mu_g * e / Lg
    return 1.0 / d if d > 0.05 else float("inf")


# ----------------------------------------------------------------------------------------------------------
# Design objects built from params.json (seal block) and the frozen bore
# ----------------------------------------------------------------------------------------------------------
_TABLES: dict = {}


def _table(kind, key, builder, dmax, step):
    if key not in _TABLES:
        ds = np.arange(0.0, dmax + 1e-9, step)
        fp, bb, pm = [], [], []
        for d in ds:
            if d < 1e-9:
                fp.append(0.0)
                bb.append(0.0)
                pm.append(0.0)
                continue
            r = ring_fe(builder(float(d)), E=1.0, nu=0.49, h=0.025)
            fp.append(r["Fp"])
            bb.append(r["b"])
            pm.append(r["p_mean"])
        _TABLES[key] = (ds, np.array(fp), np.array(bb), np.array(pm))
    return _TABLES[key]


def bead_table(groove_w, gd, clr, land, flank, dmax=0.13, step=0.01):
    """F'/E [mm], contact width [mm] and mean pressure / E for net interference 0..dmax (cached; one FE solve per grid point)."""
    key = ("bead", round(groove_w, 4), round(gd, 4), round(clr, 4), round(land, 4), round(flank, 4))
    return _table("bead", key, lambda d: v_bead_profile(groove_w, gd, clr, d, land, flank), dmax, step)


def band_table(groove_w, gd, clr, dmax=0.2, step=0.02):
    """Same for the superseded full-width band ring (reference design)."""
    key = ("band", round(groove_w, 4), round(gd, 4), round(clr, 4))
    return _table("band", key, lambda d: flat_band_profile(groove_w, gd, clr, d), dmax, step)


class SealDesign:
    """One plunger seal variant: geometry from params.json, loads from the FE table.  All lengths mm, forces N, pressures MPa."""

    def __init__(self, P: dict, key: str | None = None, legacy: bool = False, shrink: float = 0.002):
        rs, sl, fz = P["reservoir"], P["seal"], P["reservoir_frozen"]
        self.P = P
        self.legacy = legacy
        self.w_in, self.h_in = fz["bore_w"], fz["bore_h"]
        self.tol_plus = fz["bore_tol_plus"]
        self.shrink = shrink
        if legacy:      # design before the 2026-11-19 seal study: two full-width 0.8 mm bands, 0.3 oversize, core clearance 0.2, groove 0.5
            self.key, self.rings, self.oversize, self.shore = "old", ["a", "b"], 0.30, 40.0
            self.gw, self.gd, self.clr, self.land, self.flank = 0.8, 0.5, 0.2, 0.8, 0.0
            self.table = band_table(self.gw, self.gd, self.clr)
            self.L_g = 3.8 - 0.8                 # old core 3.8 long, bands at 0.6-1.4 / 2.3-3.1: contact span ~ 3.0
            clr_g = 0.2
        else:
            key = key or sl["active_variant"]
            v = sl["variants"][key]
            self.key, self.rings, self.oversize, self.shore = key, v["rings"], v["free_oversize"], float(v["shore_target"])
            self.gw = sl["ring_a"][1] - sl["ring_a"][0]
            self.gd, self.clr = sl["groove_depth"], rs["plunger_clr"]
            self.land = v.get("land", sl["land"])
            self.flank = (self.gw - self.land) / 2.0
            self.table = bead_table(self.gw, self.gd, self.clr, self.land, self.flank)
            # guide span: centre of the rear flange -> centre of the front flange of the core
            self.L_g = (rs["plunger_len"] - (rs["plunger_len"] - sl["ring_b"][1]) / 2) - sl["ring_a"][0] / 2
            clr_g = rs["plunger_clr"]
        self.n = len(self.rings)
        # contact line of the stainless shim in the plunger socket: centroid at y_end - socket_depth/2 from the plunger axis
        self.e = (self.w_in / 2 - clr_g) - sl["socket_depth"] / 2 + 0.05

    def delta(self, dbore=None, over=None, shrink=None):
        """Net radial interference per side [mm] (cast oversize minus shrink minus bore enlargement)."""
        dbore = self.tol_plus / 2 if dbore is None else dbore
        over = self.oversize if over is None else over
        shrink = self.shrink if shrink is None else shrink
        return (over - shrink * self.w_in - dbore) / 2.0

    def line_load(self, delta, shore):
        """(F' [N/mm], contact width [mm], mean pressure [MPa]) for arrays/scalars of delta and Shore A."""
        ds, fp, bb, pm = self.table
        d = np.clip(delta, 0.0, ds[-1])
        E = gent_E(shore)
        return E * np.interp(d, ds, fp), np.interp(d, ds, bb), E * np.interp(d, ds, pm)

    def perim(self, dbore=None):
        dbore = self.tol_plus / 2 if dbore is None else dbore
        return perim_stadium(self.w_in + dbore, self.h_in + dbore)

    def friction(self, mu, shore=None, dbore=None, over=None, mu_g=0.15, Lg=None):
        """Kinetic force at the plunger [N]: seal only and with the eccentric-push (cocking) amplification."""
        shore = self.shore if shore is None else shore
        dl = self.delta(dbore, over)
        Fp, b, pm = self.line_load(dl, shore)
        N = Fp * self.perim(dbore) * self.n
        F = mu * N
        Lg = self.L_g if Lg is None else Lg
        fc = cocking_factor(mu_g, self.e, Lg)
        return {"F_seal": F, "N": N, "Fp": Fp, "b": b, "p_mean": pm, "delta": dl, "E": gent_E(shore), "f_cock": fc, "F_push": F * fc,
                "perim": self.perim(dbore), "n": self.n, "e": self.e, "L_g": Lg}


def _tri(rng, t, n):
    return rng.triangular(t[0], t[1], t[2], n)


def monte_carlo(design, C, rng, N=20000, mu=None, mu_g=None, brk=None):
    """Tolerance / friction Monte Carlo of one seal design.  Returns arrays: F_seal, F_push, F_break, p_mean, delta."""
    mu = C["mu_seal_design"] if mu is None else mu
    mu_g = C["mu_guide"] if mu_g is None else mu_g
    brk = C["breakaway"] if brk is None else brk
    dbore = rng.uniform(0, design.tol_plus, N)
    over = design.oversize + rng.triangular(-C["mould_tol_diam"], 0, C["mould_tol_diam"], N)
    shrink = _tri(rng, C["shrink_range"], N)
    shore = design.shore + rng.triangular(-C["shore_scatter"], 0, C["shore_scatter"], N)
    delta = (over - shrink * design.w_in - dbore) / 2.0
    Fp, b, pm = design.line_load(delta, shore)
    per = perim_stadium(design.w_in + dbore, design.h_in + dbore)
    Fs = _tri(rng, mu, N) * Fp * per * design.n
    d = 1.0 - 2.0 * _tri(rng, mu_g, N) * design.e / design.L_g
    fc = np.where(d > 0.05, 1.0 / np.maximum(d, 0.05), 20.0)
    Fpush = Fs * fc
    return {"F_seal": Fs, "F_push": Fpush, "F_break": _tri(rng, brk, N) * Fpush, "p_mean": pm, "delta": delta, "b": b}
