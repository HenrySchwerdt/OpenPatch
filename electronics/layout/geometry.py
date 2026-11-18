"""Gemeinsame Geometrie: liest mechanical/out/<VARIANT>.layout.json und mechanical/params.json (nur lesend)
und rechnet den PCB-Umriss genau wie mechanical/op_build.py::build_electronics (Koordinaten im Mechanik-Frame:
x = Laenge, y = Breite, z = Hoehe ueber Boden; Ursprung = Aussenecke des Gehaeuses)."""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
MECH = os.path.abspath(os.path.join(HERE, "..", "..", "mechanical"))

def load(variant="OP-100"):
    L = json.load(open(os.path.join(MECH, "out", variant + ".layout.json")))
    p = json.load(open(os.path.join(MECH, "params.json")))
    wall, m = L["wall"], p["battery"]["margin"]
    pc, co, bt, bz, sp = p["pcb"], p["coil"], p["battery"], p["buzzer"], p["septum"]
    G = dict(variant=variant, L=L, p=p)
    G["housing"] = (L["length"], L["width"], L["height"])
    G["pcb"] = dict(x0=L["x_r1"] + co["gap_x"], x1=L["x_end"] - pc["margin"], y0=wall + pc["margin"], y1=L["yi1"] - pc["margin"],
                    r=p["shell"]["corner_r"] - wall - pc["margin"], z0=pc["z0"], t=pc["t"], keepout=pc["keepout"])
    G["notch"] = dict(x1=L["x_r1"] + pc["notch_x"] + (sp["boss_d"] / 2 - 0.6), y1=wall + pc["notch_y"] + 0.4)  # ab pcb.x0/y0
    G["battery"] = dict(x0=L["x_r1"] + m, x1=L["x_r1"] + m + L["bat_x"], y0=L["yi1"] - m - bt["y"], y1=L["yi1"] - m,
                        z0=wall + p["fit"]["bat_gap"], t=bt["t"])
    G["coil"] = dict(cx=L["coil_cx"], cy=L["coil_cy"], d=co["d"], z0=co["z0"], t=co["t"])
    bx1 = L["x_end"] - bz["edge_gap"]
    G["buzzer"] = dict(x0=bx1 - bz["x"], x1=bx1, y0=bz["y0"], y1=bz["y0"] + bz["y"], z0=pc["z0"] + pc["t"], h=bz["z"])
    G["reservoir"] = dict(x0=L["x_r0"], x1=L["x_r1"], y0=L["y_r0"], y1=L["y_r0"] + L["res_w_out"])
    G["spindle_y"] = L["y_s"]; G["motor"] = dict(y=L["y_m"], d=p["drive"]["motor_d"], z=L["z_axis"])
    G["needle"] = (L["x_n"], L["y_n"]); G["tower_top"] = p["cannula"].get("tower_top", 4.8) if "tower_top" in p["cannula"] else 4.8
    return G
