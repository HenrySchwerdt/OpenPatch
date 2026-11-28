"""Blender product renders of the cart pump A v2 package study. TEST ONLY - water only, never on a person.

Run (from this folder, after package.py):
  /Applications/Blender.app/Contents/MacOS/Blender -b -P render.py -- [views...]
Views: hero_front hero_rear xray top bottom. Meshes come from ../out/cart_a_v2 (mm), the scene is in metres.
"""
import math
import sys
from pathlib import Path

import bmesh
import bpy
from mathutils import Vector

HERE = Path(__file__).resolve().parent
SRC = HERE.parent / "out" / "cart_a_v2"
DST = HERE / "renders"
HDRI = next(Path(bpy.utils.resource_path("LOCAL")).glob("datafiles/studiolights/world/studio.exr"), None)
MM = 0.001
QUICK = "--quick" in sys.argv
LIGHT = float(next((a.split("=")[1] for a in sys.argv if a.startswith("--light=")), "1.0"))

# form numbers shared with package.py (kept in sync by hand: package.py is the source)
BUTTON_XY, LED_XY, USB_X, USB_Z = (46.5, 22.05), (39.0, 22.05), 42.0, 9.90   # v2.3: seam = FACE4 bore height 9.90
TOP_BUTTON, TOP_LED, FAR_WALL_Y, SEAM_Z = 19.0, 19.0, 38.0, 9.90

COLORS = {
    "shell": ((0.86, 0.85, 0.82, 1), 0.42, 0.0), "base": ((0.055, 0.058, 0.064, 1), 0.5, 0.0),
    "accent": ((0.12, 0.42, 0.45, 1), 0.35, 0.0),
    "adapter": ((0.025, 0.025, 0.028, 1), 0.35, 0.0), "steel": ((0.75, 0.76, 0.78, 1), 0.22, 1.0),
    "alu": ((0.80, 0.81, 0.82, 1), 0.3, 1.0), "brass": ((0.80, 0.62, 0.30, 1), 0.28, 1.0),
    "motor": ((0.70, 0.71, 0.73, 1), 0.3, 1.0), "motor_head": ((0.55, 0.56, 0.58, 1), 0.35, 1.0),
    "magnet": ((0.45, 0.46, 0.48, 1), 0.3, 1.0), "pcb": ((0.06, 0.30, 0.16, 1), 0.35, 0.0),
    "black": ((0.03, 0.03, 0.03, 1), 0.45, 0.0), "rubber": ((0.06, 0.06, 0.07, 1), 0.6, 0.0),
    "plastic_dark": ((0.12, 0.13, 0.14, 1), 0.45, 0.0), "cell": ((0.20, 0.32, 0.55, 1), 0.35, 0.3),
    "led": ((1.0, 1.0, 1.0, 1), 0.2, 0.0),
}


def clear() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mat_principled(name: str, color, rough: float, metal: float, **extra) -> bpy.types.Material:
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = color
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    for k, v in extra.items():
        b.inputs[k].default_value = v
    return m


def mat_ghost(name: str) -> bpy.types.Material:
    """X-ray shell: transparent in the middle, milky at grazing angles."""
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    mix = nt.nodes.new("ShaderNodeMixShader")
    tr = nt.nodes.new("ShaderNodeBsdfTransparent")
    pr = nt.nodes.new("ShaderNodeBsdfPrincipled")
    pr.inputs["Base Color"].default_value = (0.92, 0.93, 0.95, 1)
    pr.inputs["Roughness"].default_value = 0.3
    lw = nt.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    ramp = nt.nodes.new("ShaderNodeMapRange")
    ramp.inputs["To Min"].default_value = 0.03
    ramp.inputs["To Max"].default_value = 0.45
    nt.links.new(lw.outputs["Facing"], ramp.inputs["Value"])
    nt.links.new(ramp.outputs["Result"], mix.inputs["Fac"])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[1])
    nt.links.new(pr.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return m


def materials() -> dict:
    M = {k: mat_principled(k, *v) for k, v in COLORS.items()}
    M["glass"] = mat_principled("glass", (1, 1, 1, 1), 0.02, 0.0, **{"Transmission Weight": 1.0, "IOR": 1.5})
    M["water"] = mat_principled("water", (0.80, 0.90, 1.0, 1), 0.02, 0.0, **{"Transmission Weight": 1.0, "IOR": 1.33})
    M["clear"] = mat_principled("clear", (0.85, 1.0, 0.98, 1), 0.1, 0.0, **{"Transmission Weight": 0.6, "Emission Color": (0.35, 0.95, 0.85, 1),
                                                                         "Emission Strength": 2.5})
    M["led"] = M["clear"]
    M["ghost"] = mat_ghost("ghost")
    return M


def imp(path: Path, name: str) -> bpy.types.Object:
    bpy.ops.wm.stl_import(filepath=str(path))
    ob = bpy.context.selected_objects[0]
    ob.name = name
    ob.scale = (MM, MM, MM)
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return ob


def smooth(ob: bpy.types.Object, angle: float = 32.0) -> None:
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    try:
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(angle))
    except Exception:
        bpy.ops.object.shade_smooth()


def boolean(target: bpy.types.Object, cutter: bpy.types.Object, op: str = "DIFFERENCE", keep: bool = False) -> None:
    mod = target.modifiers.new("bool", "BOOLEAN")
    mod.operation = op
    mod.object = cutter
    mod.solver = "EXACT"
    bpy.context.view_layer.objects.active = target
    bpy.ops.object.modifier_apply(modifier=mod.name)
    if not keep:
        bpy.data.objects.remove(cutter, do_unlink=True)


def mesh_from_loops(name: str, loops: list[list[tuple]]) -> bpy.types.Object:
    """Closed mesh lofted through point loops (same count each), capped at both ends. Points in mm."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    rings = [[bm.verts.new(Vector(p) * MM) for p in lp] for lp in loops]
    n = len(loops[0])
    for a, b in zip(rings[:-1], rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], b[j], b[i]))
    bm.faces.new(rings[0][::-1])
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.collection.objects.link(ob)
    return ob


def stadium(cx: float, cz: float, w: float, h: float, y: float, n: int = 12) -> list[tuple]:
    r, half = h / 2, (w - h) / 2
    pts = []
    for i in range(n + 1):
        a = -math.pi / 2 + math.pi * i / n
        pts.append((cx + half + r * math.cos(a), y, cz + r * math.sin(a)))
    for i in range(n + 1):
        a = math.pi / 2 + math.pi * i / n
        pts.append((cx - half + r * math.cos(a), y, cz + r * math.sin(a)))
    return pts


def circle_loop(cx: float, cy: float, d: float, z: float, n: int = 40) -> list[tuple]:
    return [(cx + d / 2 * math.cos(2 * math.pi * i / n), cy + d / 2 * math.sin(2 * math.pi * i / n), z) for i in range(n)]


def box_obj(name: str, x, y, z) -> bpy.types.Object:
    loops = [[(x[0], y[0], zz), (x[1], y[0], zz), (x[1], y[1], zz), (x[0], y[1], zz)] for zz in z]
    return mesh_from_loops(name, loops)


def build_body(M: dict) -> bpy.types.Object:
    body = imp(SRC / "body_outer.stl", "body")
    # v2.3: no seam groove (owner: not seamless); the halves butt flush, the colour split below marks the seam
    # USB-C: stadium in the connector's own shape (8.94 x 3.26 + 0.25 per side), 45 deg chamfer outside
    w, h = 8.94 + 0.5, 3.26 + 0.5
    usb = mesh_from_loops("usb_cut", [stadium(USB_X, USB_Z, w, h, FAR_WALL_Y - 2.2), stadium(USB_X, USB_Z, w, h, FAR_WALL_Y - 0.5),
                                      stadium(USB_X, USB_Z, w + 3.0, h + 3.0, FAR_WALL_Y + 1.0)])
    boolean(body, usb)
    # button + LED holes on the flat top
    bx, by = BUTTON_XY
    boolean(body, mesh_from_loops("btn_cut", [circle_loop(bx, by, 5.6, 12.0), circle_loop(bx, by, 5.6, 20.0)]))
    lx, ly = LED_XY
    boolean(body, mesh_from_loops("led_cut", [circle_loop(lx, ly, 2.2, 12.0), circle_loop(lx, ly, 2.2, 20.0)]))
    # sounder port: three slots in the floor
    for k, y in enumerate((24.6, 26.0, 27.4)):
        boolean(body, box_obj(f"snd{k}", (53.5, 58.5), (y - 0.35, y + 0.35), (-1.0, 2.0)))
    bm = bmesh.new()                                       # split the faces exactly at the seam for a clean colour line
    bm.from_mesh(body.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, SEAM_Z * MM), plane_no=(0, 0, 1))
    bm.to_mesh(body.data)
    bm.free()
    body.data.materials.clear()                            # booleans leave an empty slot behind
    body.data.materials.append(M["shell"])
    body.data.materials.append(M["base"])
    for poly in body.data.polygons:                        # two-tone: white top half, graphite bottom half (slims the side view)
        poly.material_index = 0 if poly.center.z > SEAM_Z * MM else 1
    smooth(body)
    bpy.data.objects.remove(bpy.data.objects["body_inset"], do_unlink=True) if "body_inset" in bpy.data.objects else None
    return body


def build_details(M: dict) -> list[bpy.types.Object]:
    bx, by = BUTTON_XY
    cap = mesh_from_loops("button_cap", [circle_loop(bx, by, 5.0, TOP_BUTTON - 1.6), circle_loop(bx, by, 5.0, TOP_BUTTON - 0.25),
                                         circle_loop(bx, by, 4.4, TOP_BUTTON - 0.12)])
    cap.data.materials.append(M["accent"])
    lx, ly = LED_XY
    pipe = mesh_from_loops("light_pipe", [circle_loop(lx, ly, 2.0, TOP_LED - 3.0), circle_loop(lx, ly, 2.0, TOP_LED - 0.06)])
    pipe.data.materials.append(M["clear"])
    for o in (cap, pipe):
        smooth(o)
    return [cap, pipe]


def usb_receptacle(M: dict) -> list[bpy.types.Object]:
    """USB-C receptacle for the renders: stadium metal shell (8.94 x 3.26, 0.3 wall) with its cavity and the contact tongue."""
    y1 = FAR_WALL_Y - 1.2 - 0.05                           # front face just behind the inner wall
    shell = mesh_from_loops("usb_shell", [stadium(USB_X, USB_Z, 8.94, 3.26, y1 - 7.35), stadium(USB_X, USB_Z, 8.94, 3.26, y1)])
    cav = mesh_from_loops("usb_cav", [stadium(USB_X, USB_Z, 8.34, 2.66, y1 - 6.5), stadium(USB_X, USB_Z, 8.34, 2.66, y1 + 1.0)])
    boolean(shell, cav)
    shell.data.materials.append(M["steel"])
    tongue = box_obj("usb_tongue", (USB_X - 3.3, USB_X + 3.3), (y1 - 6.5, y1 - 0.9), (USB_Z - 0.35, USB_Z + 0.35))
    tongue.data.materials.append(M["plastic_dark"])
    return [shell, tongue]


def import_shells(M: dict) -> dict:
    """The real print parts from shells.py (placed): graphite bottom half, white top half, plunger, light pipe."""
    P = SRC / "print"
    obs = {}
    for nm, mat in (("bottom", "base"), ("top", "shell"), ("button_plunger", "accent"), ("light_pipe", "clear")):
        o = imp(P / f"placed_{nm}.stl", nm)
        o.data.materials.append(M[mat])
        smooth(o)
        obs[nm] = o
    return obs


def import_all(M: dict, xray: bool) -> dict:
    use_shells = (SRC / "print" / "placed_top.stl").exists()
    obs = import_shells(M) if use_shells else {"body": build_body(M)}
    if not use_shells:                                     # v2.2: the lock face zone is part of the shell halves
        obs["head"] = imp(SRC / "head.stl", "head")
        obs["head"].data.materials.append(M["base"])
        smooth(obs["head"])
    obs["adapter"] = imp(SRC / "adapter.stl", "adapter")
    obs["adapter"].data.materials.append(M["adapter"])
    smooth(obs["adapter"])
    obs["needle"] = imp(SRC / "needle.stl", "needle")
    obs["needle"].data.materials.append(M["steel"])
    for o in ([] if use_shells else build_details(M)) + usb_receptacle(M):
        obs[o.name] = o
    for f in sorted(SRC.glob("part__*.stl")) + sorted(SRC.glob("feat__*.stl")):
        _, nm, mat = f.stem.split("__")
        if mat == "ko" or nm in ("button_plunger", "light_pipe") or (use_shells and (f.name.startswith("feat__") or nm == "yoke")):
            continue
        o = imp(f, nm)
        o.data.materials.append(M["shell"] if mat == "shell" else M.get(mat, M["black"]))
        smooth(o)
        o.hide_render = (not xray and mat != "shell") or nm == "usb_c"    # usb_c box replaced by the modelled receptacle
        obs[nm] = o
    if use_shells:                                         # the real yoke (nut pocket, stem boss) instead of the package block
        o = imp(SRC / "print" / "placed_yoke.stl", "yoke")
        o.data.materials.append(M["plastic_dark"])
        o.hide_render = not xray
        obs["yoke"] = o
    if xray:
        for k in ("body", "bottom", "top", "head", "adapter"):
            if k in obs:
                for i in range(len(obs[k].data.materials)):
                    obs[k].data.materials[i] = M["ghost"]
        for k, o in obs.items():
            if k.startswith(("partition", "chamber_seal", "head_boss")):
                o.data.materials[0] = M["ghost"]
    return obs


def stage() -> None:
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    try:
        prefs = bpy.context.preferences.addons["cycles"].preferences
        prefs.compute_device_type = "METAL"
        prefs.get_devices()
        for d in prefs.devices:
            d.use = True
        sc.cycles.device = "GPU"
    except Exception:
        pass
    sc.cycles.samples = 32 if QUICK else 110
    sc.cycles.use_denoising = True
    sc.render.resolution_x, sc.render.resolution_y = (900, 563) if QUICK else (1800, 1125)
    try:
        sc.view_settings.view_transform = "AgX"
        sc.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        pass
    w = bpy.data.worlds.new("world")
    sc.world = w
    w.use_nodes = True
    nt = w.node_tree
    bg = nt.nodes["Background"]
    if HDRI:
        env = nt.nodes.new("ShaderNodeTexEnvironment")
        env.image = bpy.data.images.load(str(HDRI))
        nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = 0.45
    bpy.ops.mesh.primitive_plane_add(size=3.0, location=(0.04, 0.024, 0))
    floor = bpy.context.object
    floor.data.materials.append(mat_principled("floor", (0.50, 0.51, 0.52, 1), 0.8, 0.0))
    for nm, loc, size, power in (("key", (0.16, -0.20, 0.32), 0.28, 1.8 * LIGHT), ("fill", (-0.25, -0.12, 0.16), 0.35, 0.6 * LIGHT),
                                 ("rim", (-0.05, 0.30, 0.22), 0.22, 1.2 * LIGHT)):
        bpy.ops.object.light_add(type="AREA", location=loc)
        lt = bpy.context.object
        lt.name = nm
        lt.data.size = size
        lt.data.energy = power
        look_at(lt, Vector((0.04, 0.024, 0.008)))


def insight_outline(M: dict) -> None:
    """Accu-Chek Insight footprint 84 x 52 (user manual App. A) as a thin frame on the floor, its adapter end on ours (x 81.36)."""
    x1, x0, y0 = 81.36, 81.36 - 84.0, 24.5 - 26.0
    y1 = y0 + 52.0
    t = 0.5
    frame = mat_principled("insight_line", (0.85, 0.25, 0.12, 1), 0.5, 0.0, **{"Emission Color": (0.85, 0.25, 0.12, 1), "Emission Strength": 0.6})
    for k, (xr, yr) in enumerate((((x0, x1), (y0, y0 + t)), ((x0, x1), (y1 - t, y1)), ((x0, x0 + t), (y0, y1)), ((x1 - t, x1), (y0, y1)))):
        o = box_obj(f"insight{k}", xr, yr, (0.01, 0.06))
        o.data.materials.append(frame)


def look_at(ob: bpy.types.Object, target: Vector) -> None:
    d = target - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


VIEWS = {   # direction from the target, distance (m), lens (mm), target (m)
    "hero_front": ((0.95, -0.85, 0.48), 0.25, 70, (0.043, 0.024, 0.008)),
    "hero_rear": ((-0.85, 0.95, 0.75), 0.26, 70, (0.038, 0.026, 0.007)),
    "xray": ((0.55, -0.75, 1.05), 0.27, 70, (0.040, 0.024, 0.006)),
    "top": ((0.0, -0.001, 1.0), 0.36, 85, (0.038, 0.025, 0.0)),
    "usb": ((-0.30, 1.0, 0.32), 0.075, 70, (0.041, 0.038, 0.0088)),
}


def render(view: str) -> None:
    clear()
    M = materials()
    stage()
    import_all(M, xray=(view == "xray"))
    if view == "top":
        insight_outline(M)
    dirn, dist, lens, tgt = VIEWS[view]
    tgt = Vector(tgt)
    bpy.ops.object.camera_add(location=tgt + Vector(dirn).normalized() * dist)
    cam = bpy.context.object
    cam.data.lens = lens
    cam.data.clip_start = 0.002
    look_at(cam, tgt)
    bpy.context.scene.camera = cam
    DST.mkdir(parents=True, exist_ok=True)
    bpy.context.scene.render.filepath = str(DST / f"v2_{view}.png")
    bpy.ops.render.render(write_still=True)


if __name__ == "__main__":
    args = [a for a in (sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []) if not a.startswith("--")] or list(VIEWS)
    for v in args:
        render(v)
