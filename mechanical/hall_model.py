"""Small magnet field model used for the bench-pod sensor placement (pure Python, no numpy).

Diametric cylinder magnet (axis X) modelled as lateral surface charges; axial disc magnet via the closed on-axis formula.
Estimates only (+-20 %): use them to place sensors, then measure on the bench.
"""
from __future__ import annotations

import math


def diametric_field_mT(pos: tuple[float, float, float], theta: float, br_t: float = 1.3,
                       r: float = 1.0, t: float = 1.0, nphi: int = 72, nx: int = 6) -> tuple[float, float, float]:
    """B (mT) at pos = (dx, dy, dz) from the magnet centre; magnetisation (0, sin th, cos th) perpendicular to the X axis."""
    my, mz = math.sin(theta), math.cos(theta)
    bx = by = bz = 0.0
    da = (r * 2 * math.pi / nphi) * (t / nx)
    for j in range(nphi):
        ph = 2 * math.pi * j / nphi
        cy, cz = math.cos(ph), math.sin(ph)
        sig = br_t * (cy * my + cz * mz)
        for i in range(nx):
            x = (i + 0.5) / nx * t - t / 2
            dx, dy, dz = pos[0] - x, pos[1] - r * cy, pos[2] - r * cz
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            k = sig * da / d ** 3 / (4 * math.pi)
            bx += k * dx
            by += k * dy
            bz += k * dz
    return bx * 1000, by * 1000, bz * 1000


def bz_phase_amp(pos: tuple[float, float, float], n: int = 24, br_t: float = 1.3, r: float = 1.0, t: float = 1.0) -> tuple[float, float]:
    """Fundamental of B_z(theta) of a sensor at pos: (phase in deg, amplitude in mT)."""
    c = s = 0.0
    for k in range(n):
        th = 2 * math.pi * k / n
        b = diametric_field_mT(pos, th, br_t, r, t)[2]
        c += b * math.cos(th)
        s += b * math.sin(th)
    c *= 2 / n
    s *= 2 / n
    return math.degrees(math.atan2(s, c)), math.hypot(c, s)


def axial_disc_on_axis_mT(z_from_surface: float, br_t: float = 1.3, r: float = 1.0, t: float = 1.0) -> float:
    """On-axis B (mT) of an axially magnetised disc at distance z from its face."""
    a = z_from_surface + t
    return br_t / 2 * (a / math.hypot(r, a) - z_from_surface / math.hypot(r, z_from_surface)) * 1000


def axial_trigger_distance_mm(b_mT: float, br_t: float = 1.3, r: float = 1.0, t: float = 1.0) -> float:
    lo, hi = 0.0, 20.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if axial_disc_on_axis_mT(mid, br_t, r, t) > b_mT:
            lo = mid
        else:
            hi = mid
    return lo
