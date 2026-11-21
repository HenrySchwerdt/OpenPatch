#!/usr/bin/env python3
"""Functional 2:1 demonstrator parts for FDM printing (0.4 mm nozzle): toothed miter gears, a threaded lead screw and its nut.

The pod CAD carries the gears as envelopes and the rod / nut without threads (they are bought parts). For a hand-turned 2:1 print
these three parts are generated here with real geometry, scaled from the 1:1 design (mechanical/V010-CUP.md):
  * miter pair m0.3 z12 -> m0.6 z12, 20 deg, conical (Tredgold-style) extrusion of the involute section, 0.15 mm backlash,
    face from 2.4 to 3.6 mm along the axis from the apex (1:1: front 1.2, pitch circle 1.8), hub d5.6;
    gear A bore d4.2 (motor shaft dummy d4), gear B bore d3.4 (glued on the plain end of the rod)
  * lead screw M1.6 x 0.35 -> d3.2, but with a printable 1.0 mm pitch, 60 deg profile 0.45 deep, 32.8 mm long, first 7 mm plain
  * nut DIN 934 AF 3.5 -> AF 7.0 x 2.6, internal thread to the rod with 0.2 mm radial clearance
Print the rod upright in PETG (two copies; it is 3.2 mm thin), gears back face down at 0.1 mm layers. Demonstrator only.

usage: python3 demo_2to1.py <out dir>
"""
import math
import os
import sys

import numpy as np
import trimesh
import manifold3d as mf

S = 2.0
M, Z, PA, BACKLASH = 0.3 * S, 12, 20.0, 0.15
A_IN, A_OUT = 1.2 * S, 1.8 * S             # tooth face along the gear axis, measured from the cone apex
HUB_D = 2.8 * S
BACK = {"gear_a": 3.4 * S, "gear_b": 3.32 * S}
BORE = {"gear_a": 4.2, "gear_b": 3.4}
ROD_D, ROD_L, PITCH, DEPTH, PLAIN = 1.6 * S, 16.4 * S, 1.0, 0.45, 7.0
NUT_AF, NUT_H, NUT_CLR = 3.5 * S, 1.3 * S, 0.20


def involute_section(m, z, pa_deg, backlash, n_inv=12, n_root=4):
    """closed outline of a spur gear (pitch radius m z / 2) in the transverse plane, CCW"""
    pa = math.radians(pa_deg)
    rp = m * z / 2
    rb = rp * math.cos(pa)
    ra = rp + m
    rf = rp - 1.25 * m
    inv = lambda a: math.tan(a) - a
    # half tooth thickness angle at the pitch circle
    s_half = (math.pi * m / 2 - backlash / 2) / (2 * rp)
    pts = []
    for k in range(z):
        c = 2 * math.pi * k / z
        flank = []
        for i in range(n_inv + 1):
            r = max(rb, rf) + (ra - max(rb, rf)) * i / n_inv
            ap = math.acos(min(rb / r, 1.0))
            ang = s_half + inv(pa) - inv(ap)
            flank.append((r, ang))
        right = [(r * math.cos(c - a), r * math.sin(c - a)) for r, a in flank]
        left = [(r * math.cos(c + a), r * math.sin(c + a)) for r, a in reversed(flank)]
        if rf < rb:
            a0 = flank[0][1]
            right.insert(0, (rf * math.cos(c - a0), rf * math.sin(c - a0)))
            left.append((rf * math.cos(c + a0), rf * math.sin(c + a0)))
        pts += right + left
        # root arc to the next tooth
        a_end = c + (flank[0][1])
        a_next = c + 2 * math.pi / z - flank[0][1]
        for i in range(1, n_root):
            a = a_end + (a_next - a_end) * i / n_root
            pts.append((rf * math.cos(a), rf * math.sin(a)))
    return pts


def gear(name):
    sec = mf.CrossSection([involute_section(M, Z, PA, BACKLASH)])
    # pitch radius at axial distance a from the apex equals a (45 deg cone): the section at A_OUT has rp = A_OUT
    rp = M * Z / 2
    sec_out = sec.scale((A_OUT / rp, A_OUT / rp))
    teeth = mf.Manifold.extrude(sec_out, A_OUT - A_IN, n_divisions=8, scale_top=(A_IN / A_OUT, A_IN / A_OUT))
    # teeth run from z = 0 (back of the face, a = A_OUT) to z = A_OUT - A_IN (front, a = A_IN)
    hub_len = BACK[name] - A_OUT
    hub = mf.Manifold.cylinder(hub_len, HUB_D / 2, HUB_D / 2, 64).translate((0, 0, -hub_len))
    root = mf.Manifold.cylinder(A_OUT - A_IN, (A_OUT - 1.25 * M * A_OUT / rp), (A_IN - 1.25 * M * A_IN / rp), 64)
    body = teeth + hub + root
    bore = mf.Manifold.cylinder(BACK[name] + 2, BORE[name] / 2, BORE[name] / 2, 48).translate((0, 0, -BACK[name] - 1))
    g = (body - bore).translate((0, 0, hub_len))          # back face on the bed (z = 0)
    return g


def threaded_cylinder(r_major, depth, pitch, length, z0=0.0, plain=0.0, n_theta=96, dz=0.05):
    """watertight mesh: thread from z0 + plain to z0 + length (60 deg-ish trapezoid), plain cylinder (r_major) below that"""
    nz = int(round(length / dz)) + 1
    zs = np.linspace(0, length, nz)
    th = np.linspace(0, 2 * np.pi, n_theta, endpoint=False)
    T, Zg = np.meshgrid(th, zs)
    u = ((Zg - pitch * T / (2 * np.pi)) / pitch) % 1.0
    prof = np.clip(np.minimum(u, 1 - u) * 4 - 0.5, 0, 1)        # flat crest 25 %, flanks, flat root 25 %
    R = r_major - depth * (1 - prof)
    R[Zg < plain] = r_major
    X, Y = R * np.cos(T), R * np.sin(T)
    V = np.stack([X.ravel(), Y.ravel(), (Zg + z0).ravel()], 1)
    F = []
    idx = lambda j, i: j * n_theta + (i % n_theta)
    for j in range(nz - 1):
        for i in range(n_theta):
            a, b, c, d = idx(j, i), idx(j, i + 1), idx(j + 1, i + 1), idx(j + 1, i)
            F += [(a, b, c), (a, c, d)]
    c0 = len(V); V = np.vstack([V, [0, 0, z0], [0, 0, z0 + length]]); c1 = c0 + 1
    for i in range(n_theta):
        F.append((c0, idx(0, i + 1), idx(0, i)))
        F.append((c1, idx(nz - 1, i), idx(nz - 1, i + 1)))
    m = trimesh.Trimesh(V, np.array(F), process=True)
    m.fix_normals()
    return m


def to_manifold(m):
    mesh = mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32))
    return mf.Manifold(mesh)


def to_trimesh(man):
    me = man.to_mesh()
    return trimesh.Trimesh(np.asarray(me.vert_properties)[:, :3], np.asarray(me.tri_verts), process=True)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    for name in ("gear_a", "gear_b"):
        to_trimesh(gear(name)).export(os.path.join(out, f"{name}_demo_x2.stl"))
    rod = threaded_cylinder(ROD_D / 2, DEPTH, PITCH, ROD_L, plain=PLAIN)
    rod.export(os.path.join(out, "lead_screw_demo_x2.stl"))
    # nut: hex prism minus a slightly larger threaded tool
    hexagon = mf.CrossSection.circle(NUT_AF / math.sqrt(3), 6)
    nut = mf.Manifold.extrude(hexagon, NUT_H)
    tool = to_manifold(threaded_cylinder(ROD_D / 2 + NUT_CLR, DEPTH, PITCH, NUT_H + 2, z0=-1.0, n_theta=96, dz=0.05))
    to_trimesh(nut - tool).export(os.path.join(out, "plunger_nut_demo_x2.stl"))
    for f in sorted(os.listdir(out)):
        if f.endswith("_demo_x2.stl"):
            m = trimesh.load(os.path.join(out, f))
            print(f, (m.bounds[1] - m.bounds[0]).round(2).tolist(), "watertight", m.is_watertight)


if __name__ == "__main__":
    main()
