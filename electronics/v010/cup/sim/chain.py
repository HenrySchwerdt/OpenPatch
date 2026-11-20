"""Full interlock chain deck builder: cell -> TPS61023 (behavioural) -> TPS2553 (TI model) -> motor load, plus the corrected enable logic.

Logic (coordinator revision 2026-11-20): PERM_L = LATCH_Q AND SUP_PERMIT AND MCU_EN (U36, AUP1G11), DOCK_OK = DOCK_N XOR MOT_FWD (U33, AUP1G86),
MOT_ALLOW = PERM_L AND DOCK_OK (U34), LATCH_CLR_N = SUP_NRST AND OC_OK (U32), latch U6 (AUP1G74, D = 3V3, CLK = ARM_CLK).
Pulls (netlist): R16 MOT_FWD up, R82 SUP_PERMIT down, R18 MCU_EN down (new), R29 ARM_CLK down, R90 MOT_ALLOW down, R92 OC_OK up,
SUP_NRST up = STM32C011 internal NRST pull-up (ASSUMPTION 40 k).  DOCK_N has NO pull in the netlist (finding F1); option dock_pu adds one.
"""
import simlib as S

HEAD = """.include @LIB@/tps61023_beh.inc
.include @LIB@/aup.inc
.include @LIB@/aup2.inc
.include @MODELS@/TPS2553_ng.lib
"""
SW = ".model swgpio sw vt=0.5 vh=0.1 ron=100 roff=1e13\n.model swod sw vt=0.5 vh=0.1 ron=300 roff=1e13\n"


def pwl(points):
    return "PWL(" + " ".join("%g %g" % p for p in points) + ")"


def drive(sig, wave, rail="v3v3"):
    """GPIO / push-pull driver: output = min(wave, rail) behind 100 ohm. wave=None -> high impedance (only the board pulls act)."""
    if wave is None:
        return "* %s: high impedance (not driven)\n" % sig
    return ("Vw_%s w_%s 0 %s\nB_%s d_%s 0 V = min(v(w_%s), v(%s))\nR_%s d_%s %s 100\n" % (sig, sig, wave, sig, sig, sig, rail, sig, sig, sig))


def chain(p):
    """p keys: ocv, rint, v3v3 (PWL string or number), drv {sig: wave|None}, force {sig: level} (hard stuck 1 ohm), dock_pu (ohm|None), opens (set),
    undef (0/1), latch_ic (None/0/1), nrst_bor (bool), load ('motor'|'short'), short_t, tstop, tstep, cb, c21, ic_nodes {node: V}"""
    drv = p.get("drv", {})
    force = p.get("force", {})
    opens = p.get("opens", set())
    s = "* interlock chain deck\n" + HEAD + SW
    s += "Vsrc v3src 0 %s\n" % p.get("v3v3", "3.3")
    s += "Sreg v3src v3v3 regon 0 swreg\n.model swreg sw vt=0.5 vh=0.1 ron=1 roff=1e13\nVreg regon 0 %s\n" % p.get("reg", "1")
    s += "Rv3 v3v3 0 825\nC3v3 v3v3 0 4.7u\nC19 v3v3 0 0.1u\nC50 v3v3 0 0.1u\n"     # 4 mA load (INTERLOCK I.7) + new 4.7 uF + C19/C50
    s += S.snip_cell(p.get("ocv", 3.7), p.get("rint", S.RINT_NOM))
    s += S.snip_boost("sup_permit", p.get("cb", S.CB1_EFF))
    s += S.snip_switch("mot_allow", p.get("c21", S.C21_EFF)).replace("XU20 vmot_pre 0 mot_allow 0 oc_ok ilim vmot", "XU20 vmot_pre 0 mot_allow 0 oc_ok ilim vsw")
    s += "Vsm vsw vmot 0\n"
    ua = p.get("undef", 1)
    s += "XU36 latch_q sup_permit mcu_en perm_l v3v3 0 aup_and3 params: undef=%d\n" % ua
    s += "XU33 dock_n mot_fwd dock_ok v3v3 0 aup_xor2 params: undef=%d\n" % ua
    s += "XU34 perm_l dock_ok mot_allow v3v3 0 aup_and2 params: undef=%d\n" % ua
    s += "XU32 sup_nrst oc_ok latch_clr_n v3v3 0 aup_and2 params: undef=%d\n" % ua
    s += "XU6 arm_clk v3v3 latch_q latch_clr_n v3v3 0 aup74\n"
    pulls = [("R90", "mot_allow", "0", "100k"), ("R16", "v3v3", "mot_fwd", "100k"), ("R82", "sup_permit", "0", "100k"), ("R18", "mcu_en", "0", "100k"),
             ("R29", "arm_clk", "0", "100k"), ("Rnrst", "v3v3", "sup_nrst", "40k")]
    for ref, a, b, v in pulls:
        if ref not in opens:
            s += "%s %s %s %s\n" % (ref, a, b, v)
    if p.get("dock_pu"):
        s += "Rdockpu v3v3 dock_n %g\n" % p["dock_pu"]
    # (R92 is in snip_switch; remove it when opened)
    if "R92" in opens:
        s = s.replace("R92 v3v3 oc_ok 100k\n", "")
    for r, line in (("R55", "R55 vmot_pre fb 220k\n"), ("R56", "R56 fb 0 30k\n"), ("R91", "R91 ilim 0 47000\n")):
        if r in opens:
            s = s.replace(line, "")
    for sig in ("arm_clk", "sup_permit", "mcu_en", "mot_fwd", "dock_n", "sup_nrst_dummy"):
        if sig in drv:
            s += drive(sig, drv[sig])
    for sig, lev in force.items():
        s += "Vf_%s f_%s 0 PWL(0 0 0.5m 0 0.501m %g)\nRf_%s f_%s %s 1\n" % (sig, sig, lev, sig, sig, sig)
    if p.get("rstn_wave"):     # TPL5010 open-drain RSTn (datasheet timing): pulls SUP_NRST low
        s += "Vrstn rstn_c 0 %s\nSrstn sup_nrst 0 rstn_c 0 swod\n" % p["rstn_wave"]
    if p.get("nrst_bor", True):   # STM32 holds NRST low while its supply is below its reset threshold (~1.7 V)
        s += "Bbor bor 0 V = (v(v3v3) < 1.7) ? 1 : 0\nSbor sup_nrst 0 bor 0 swod\n"
    load = p.get("load", "motor")
    rm = (S.R_COIL * p.get("rscale", 1.0) + S.R_BRIDGE) / 2
    s += "Bmot vmot 0 I = (v(v3v3) > 2.0) ? v(vmot) / %g : 0\n" % rm      # both windings on; bridges die with VCC (UVLO 2 V)
    if load == "short":
        s += "Bshort vmot 0 I = (time > %g && time < %g) ? v(vmot) / %g : 0\n" % (p.get("short_t", 25e-3), p.get("short_end", 1e9), p.get("short_r", 0.5))
    ic = []
    if True:
        ic.append("v(xu6.s)=%g v(xu6.m)=%g" % (3.3 * p.get("latch_ic", 0), 3.3 * p.get("latch_ic", 0)))
    for n, v in p.get("ic_nodes", {}).items():
        ic.append("v(%s)=%g" % (n, v))
    if ic:
        s += ".ic " + " ".join(ic) + "\n"
    s += S.SPICE_OPTS
    uic = " uic" if p.get("uic") else ""
    s += ".tran %s %s%s\n" % (p.get("tstep", "5u"), p.get("tstop", "40m"), uic)
    s += (".control\nrun\nwrdata @RES@/%s.csv v(v3v3) v(latch_q) v(sup_permit) v(mot_allow) v(vmot_pre) v(vmot) v(oc_ok) v(latch_clr_n) i(Vcell) "
          "i(Vsm) v(dock_ok) v(perm_l)\n.endc\n.end\n" % p["name"])
    return s


NAMES = ["v3v3", "latch_q", "permit", "allow", "vpre", "vmot", "ocok", "clrn", "icell", "isw", "dockok", "perml"]


def run(p, mode="ps"):
    return S.run_wave(chain(p), p["name"], NAMES, mode=mode)


def pulse(t0, w=100e-6, hi=3.3):
    return pwl([(0, 0), (t0, 0), (t0 + 1e-6, hi), (t0 + w, hi), (t0 + w + 1e-6, 0)])


def step(t0, lo=0, hi=3.3):
    return pwl([(0, lo), (t0, lo), (t0 + 1e-6, hi)])
