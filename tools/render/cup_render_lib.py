import importlib.util, sys, os
os.environ.setdefault("OP_CAD_DIR", "/Users/henryschwerdtner/dev/ai-insulin-pump-elec/mechanical/out/v010-cup")
os.environ.setdefault("OP_RENDER_WORK", os.path.dirname(__file__) + "/work")
spec = importlib.util.spec_from_file_location("rp", "/Users/henryschwerdtner/dev/ai-insulin-pump-elec/site/scripts/render-product.py")
rp = importlib.util.module_from_spec(spec); spec.loader.exec_module(rp)
P = lambda a: {"appearance": a}
rp.LOOKS = {
 "reservoir": P("starter.plastic.hdpe-natural-opaque"), "plunger_core": P("starter.plastic.abs-warm-white"),
 "seal_a": P("starter.plastic.tpu-matte-black"), "seal_b": P("starter.plastic.tpu-matte-black"),
 "nut": P("starter.metal.brass-champagne"), "gear_a": P("starter.metal.brass-champagne"), "gear_b": P("starter.metal.brass-champagne"),
 "motor": P("starter.metal.aluminum-bead-blast"), "gearhead": P("starter.metal.titanium-matte"),
 "magnet": P("starter.metal.carbon-steel-polished"), "septum": P("starter.plastic.tpu-matte-black"),
 "lid_gasket": P("starter.plastic.tpu-matte-black"), "usb_gasket": P("starter.plastic.tpu-matte-black"), "hub_oring": P("starter.plastic.tpu-matte-black"),
 "ko_battery": P("starter.plastic.pc-graphite-opaque"), "ko_usb": P("starter.metal.silver-cool"),
 "ko_board": {"color": "#1f5a3a", "pbr": {"metallic": 0.0, "roughness": 0.45, "dielectric_ior": 1.5}},
 "ko_dock_board": {"color": "#1f5a3a", "pbr": {"metallic": 0.0, "roughness": 0.45, "dielectric_ior": 1.5}},
 "ko_tmag_board": {"color": "#1f5a3a", "pbr": {"metallic": 0.0, "roughness": 0.45, "dielectric_ior": 1.5}},
 "cannula_adapter": P("starter.plastic.hdpe-natural-opaque"), "hall_tmag": P("starter.plastic.pom-black"), "hall_dock": P("starter.plastic.pom-black"),
}
rp.HIDDEN = {"ko_aux", "ko_io", "ko_side_a", "ko_side_b"}
rp.LIFT = {"top": 34, "lid_gasket": 28, "ko_board": 20, "ko_usb": 20, "ko_tmag_board": 20, "ko_dock_board": 20, "ko_battery": 13,
 "motor": 9, "gearhead": 9, "motor_boss": 9, "motor_rear_boss": 9, "motor_shaft": 9, "motor_term": 9, "gear_a": 9,
 "plunger_core": 5, "seal_a": 5, "seal_b": 5, "nut": 5, "rod": 5, "thrust_sleeve": 5, "gear_b": 5, "bush_rod": 5, "thrust_collar": 5, "magnet": 5,
 "cannula_adapter": -10, "dock_magnet": -10}
cam = dict(target=[24, 17, 4], yaw=-0.62, pitch=0.46, distance=200, fov=0.22)
rp.SHOTS = {
 "cup_hero": dict(d="OP-100", w=2400, h=1500, cam=cam, expl=False),
 "cup_hero_graphite": dict(d="OP-100", w=2400, h=1500, cam=cam, expl=False, graphite=True),
 "cup_exploded": dict(d="OP-100", w=2200, h=1700, cam=dict(target=[24, 17, 14], yaw=-0.62, pitch=0.42, distance=330, fov=0.22), expl=True),
}


