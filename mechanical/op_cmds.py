"""Small emitter for SolidCraft command scripts (JSON list of {command, params})."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

_ROOT = Path(__file__).resolve().parent


def _rel(path: str) -> str:
    """Repo-relative (mechanical/-relative) path for committed scripts; the CLI is run with cwd = mechanical/."""
    return os.path.relpath(path, _ROOT) if os.path.isabs(path) else path


class Script:
    def __init__(self) -> None:
        self.cmds: list[dict] = []

    def add(self, command: str, **params) -> None:
        self.cmds.append({"command": command, "params": params})

    def parameter(self, name: str, value: float, comment: str = "") -> None:
        self.add("parameters.add", name=name, expression=repr(round(float(value), 6)), comment=comment)

    # ---- Primitive -------------------------------------------------------------
    def box(self, name: str, x: tuple[float, float], y: tuple[float, float], z: tuple[float, float]) -> str:
        self.add("solid.box", length=x[1] - x[0], width=y[1] - y[0], height=z[1] - z[0],
                 corner=[x[0], y[0], z[0]], body_name=name, name=name)
        return name

    def cyl(self, name: str, axis: str, c: tuple[float, float, float], d: float,
            a0: float, a1: float) -> str:
        """Cylinder along 'axis' from a0 to a1; c = centre in the two other axes."""
        base = {"X": [a0, c[1], c[2]], "Y": [c[0], a0, c[2]], "Z": [c[0], c[1], a0]}[axis]
        self.add("solid.cylinder", diameter=d, height=a1 - a0, base=base, axis=axis,
                 body_name=name, name=name)
        return name

    def cone(self, name: str, axis: str, c: tuple[float, float, float], r0: float, r1: float,
             a0: float, a1: float) -> str:
        """Kegelstumpf entlang 'axis' von a0 (Radius r0) bis a1 (Radius r1); c = Mittelpunkt in den beiden anderen Achsen."""
        base = {"X": [a0, c[1], c[2]], "Y": [c[0], a0, c[2]], "Z": [c[0], c[1], a0]}[axis]
        self.add("solid.cone", radius=r0, top_radius=r1, height=a1 - a0, base=base, axis=axis,
                 body_name=name, name=name)
        return name

    def tube(self, name: str, axis: str, c: tuple[float, float, float], d_out: float, d_in: float,
             a0: float, a1: float) -> str:
        self.cyl(name, axis, c, d_out, a0, a1)
        self.cyl(f"t_{name}_bore", axis, c, d_in, a0 - 0.1, a1 + 0.1)
        self.cut(name, [f"t_{name}_bore"])
        return name

    def rrect(self, name: str, x: tuple[float, float], y: tuple[float, float], r: float,
              z: tuple[float, float]) -> str:
        self.add("sketch.create", plane="XY", offset=z[0])
        self.add("sketch.rectangle.rounded", p0=[x[0], y[0]], p1=[x[1], y[1]], radius=r)
        self.add("sketch.finish")
        self.add("solid.extrude", distance=z[1] - z[0], body_name=name, name=name)
        return name

    def polyprism(self, name: str, pts: list[tuple[float, float]], z: tuple[float, float]) -> str:
        """Closed polygon in XY (absolute mm) extruded from z[0] to z[1]."""
        self.add("sketch.create", plane="XY", offset=z[0])
        self.add("sketch.line", points=[list(q) for q in pts], closed=True)
        self.add("sketch.finish")
        self.add("solid.extrude", distance=z[1] - z[0], body_name=name, name=name)
        return name

    def prism_yz(self, name: str, pts: list[tuple[float, float]], x0: float, x1: float) -> str:
        """Polygon in (y, z) extruded along +X from x0 to x1."""
        self.add("sketch.create", plane="YZ", offset=x0)
        self.add("sketch.line", points=[[round(a, 5), round(b, 5)] for a, b in pts], closed=True)
        self.add("sketch.finish")
        self.add("solid.extrude", distance=x1 - x0, body_name=name, name=name)
        return name

    def prism_xz(self, name: str, pts: list[tuple[float, float]], y0: float, y1: float) -> str:
        """Polygon in (x, z) extruded along +Y from y0 to y1 (the XZ sketch plane maps (a, b) -> x = a, z = -b)."""
        self.add("sketch.create", plane="XZ", offset=y0)
        self.add("sketch.line", points=[[round(a, 5), round(-b, 5)] for a, b in pts], closed=True)
        self.add("sketch.finish")
        self.add("solid.extrude", distance=y1 - y0, body_name=name, name=name)
        return name

    def stadium(self, name: str, x: tuple[float, float], yc: float, zc: float,
                w: float, h: float) -> str:
        """Langloch-Querschnitt (w in Y, h in Z), extrudiert entlang +X."""
        half = (w - h) / 2
        self.add("sketch.create", plane="YZ", offset=x[0])
        self.add("sketch.slot.center_to_center", p0=[yc - half, zc], p1=[yc + half, zc], width=h)
        self.add("sketch.finish")
        self.add("solid.extrude", distance=x[1] - x[0], body_name=name, name=name)
        return name

    def stadium_taper(self, name: str, x: tuple[float, float], yc: float, zc: float,
                      w: float, h: float, taper_deg: float) -> str:
        """Stadium (w x h at x[0]) extruded to x[1] with a draft: positive grows, negative shrinks the outline per side by
        (x[1]-x[0]) * tan(taper).  Used for the flanks of the cast seal bead."""
        half = (w - h) / 2
        self.add("sketch.create", plane="YZ", offset=x[0])
        self.add("sketch.slot.center_to_center", p0=[yc - half, zc], p1=[yc + half, zc], width=h)
        self.add("sketch.finish")
        self.add("solid.extrude", distance=x[1] - x[0], taper=f"{taper_deg:.4f} deg", body_name=name, name=name)
        return name

    def stadium_ring(self, name: str, x: tuple[float, float], yc: float, zc: float,
                     w_out: float, h_out: float, w_in: float, h_in: float) -> str:
        self.stadium(name, x, yc, zc, w_out, h_out)
        self.stadium(f"t_{name}_in", (x[0] - 0.1, x[1] + 0.1), yc, zc, w_in, h_in)
        self.cut(name, [f"t_{name}_in"])
        return name

    def hexprism(self, name: str, x: tuple[float, float], yc: float, zc: float, apothem: float,
                 angle: float = 0.0) -> str:
        """Hexagonal prism along +X (width across flats = 2*apothem)."""
        self.add("sketch.create", plane="YZ", offset=x[0])
        self.add("sketch.polygon.circumscribed", center=[yc, zc], radius=apothem, sides=6, angle=angle)
        self.add("sketch.finish")
        self.add("solid.extrude", distance=x[1] - x[0], body_name=name, name=name)
        return name

    # ---- Booleans -----------------------------------------------------------------
    def cut(self, target: str, tools: Iterable[str]) -> None:
        self.add("solid.combine", target=target, tools=list(tools), operation="cut", name=f"cut {target}")

    def join(self, target: str, tools: Iterable[str]) -> None:
        self.add("solid.combine", target=target, tools=list(tools), operation="join", name=f"join {target}")

    def fillet_chain(self, body: str, point: tuple[float, float, float], r: float) -> None:
        self.add("solid.fillet", edges=[list(point)], radius=r, body=body, name=f"fillet {body}")

    def move(self, bodies: list[str], t: tuple[float, float, float]) -> None:
        self.add("solid.move", bodies=bodies, translate=list(t))

    # ---- Export -------------------------------------------------------------------
    def export_step(self, path: str, bodies: list[str] | None = None) -> None:
        if bodies:
            self.add("file.export_step", path=_rel(path), bodies=bodies)
        else:
            self.add("file.export_step", path=_rel(path))

    def export_stl(self, path: str, bodies: list[str]) -> None:
        self.add("file.export_stl", path=_rel(path), bodies=bodies, quality="fine")

    def dumps(self) -> list[dict]:
        return self.cmds
