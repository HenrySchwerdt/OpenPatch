"""Pure-Python sanity tests (no SolidCraft needed): CLI discovery, gear/ratio consistency, frozen dock interface.

  python3 -m pytest mechanical/test_layout.py
"""
from __future__ import annotations

import copy
import math
import shutil

import pytest

from generate import apply_overrides
from op_layout import compute_layout, find_cli, load_params


def bench_params() -> dict:
    p = apply_overrides(load_params(), [], None, None)
    p["mode"] = "bench"
    p["shell"]["width"] = p["bench"]["width_by_layout"][p["bench"]["drive_layout"]]
    return p


def test_find_cli_env_and_fallback(monkeypatch):
    monkeypatch.setenv("SOLIDCRAFT_CLI", "/x/solidcraft-cli")
    assert find_cli() == "/x/solidcraft-cli"
    monkeypatch.delenv("SOLIDCRAFT_CLI")
    monkeypatch.setattr(shutil, "which", lambda _n: None)
    assert find_cli().endswith("SolidCraft.app/Contents/MacOS/solidcraft-cli")


@pytest.mark.parametrize("size", ["OP-70", "OP-100", "OP-200"])
def test_gear_pair_consistent(size):
    p = bench_params()
    L = compute_layout(copy.deepcopy(p), size)
    g, gp = L["gears"], p["bench"]["gears"]
    theo = gp["module"] * (gp["z_motor"] + gp["z_screw"]) / 2
    assert g["centre"] == pytest.approx(theo + gp["centre_add"])
    assert g["centre"] >= gp["min_centre"]
    # U/step must follow the ratio screw_turns_per_motor_turn = z_motor / z_screw
    dr = p["drive_presets"]["nfp_608_26"]
    base = 0.35 / (20 * dr["gh_ratio"]) * 74.63 / 10
    assert L["drive"]["u_per_step"] == pytest.approx(base * gp["z_motor"] / gp["z_screw"], rel=1e-3)
    # motor body clears the carriage lane
    assert L["y_m"] - p["drive"]["motor_d"] / 2 >= L["y_s"] + p["drive"]["carriage_bw"] / 2 + 0.1 - 1e-9


def test_envelope_limits():
    p = bench_params()
    for size in ("OP-70", "OP-100", "OP-200"):
        L = compute_layout(copy.deepcopy(p), size)
        assert L["height"] <= p["spec"]["max_height"]
        assert L["width"] <= p["spec"]["width_target"]
        assert L["length"] <= p["bench"]["length_targets_by_layout"]["side_gears"][size]


def test_frozen_dock_interface_consistent():
    p = bench_params()
    F = p["dock_interface_frozen"]
    assert F["win_half"] < F["pocket_half"]
    assert F["mouth_half"] < F["win_half"]
    L = compute_layout(copy.deepcopy(p), "OP-100")
    # insert tail length equals the pod tail (x_end + wall - x_r1), identical for all sizes
    assert L["length"] - L["x_r1"] == pytest.approx(F["tail_u"])
    assert L["dock"]["y_c"] == pytest.approx(L["y_r"])          # needle axis = reservoir port axis
    assert math.isclose(L["dock"]["mouth_half"], F["mouth_half"])
    assert L["dock"]["strain_ok"]


def test_frozen_reservoir_unchanged():
    p = load_params()
    fz = p["reservoir_frozen"]
    assert (fz["bore_w"], fz["bore_h"], fz["wall"], fz["end_wall"], fz["port_d"]) == (16.0, 5.0, 0.8, 2.5, 2.0)
