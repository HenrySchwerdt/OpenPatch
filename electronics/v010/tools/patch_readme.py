import os
p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "README.md")
s = open(p).read()
i = s.index("| Routing / DRC |")
j = s.index("\n", i)
new = ("| Routing / DRC (split design v2, `board/flow_multi.sh`) | **SENSOR 15 x 13 mm (195 mm2, 2L, 6 parts): 100 % routed, DRC 0 errors, JLC package in `fab/jlcpcb/sensor/`. "
       "USB 22 x 26 mm (572 mm2, 2L, 10 parts): 100 % routed, DRC 0 errors, package in `fab/jlcpcb/usb/` (receptacle is a placeholder). "
       "MAIN 52 x 38 mm (1976 mm2, 4L, 177 parts): NOT complete: Freerouting 2.2.4, 6 passes (31 min): 72 connections unconnected (about 75 % routed, 348 unrouted at start), "
       "5 copper-edge errors on BTN_N/3V3; the 42 x 32 mm try left 99 unconnected. No MAIN package.** Cause: E73 + PicoBlade + buzzer + 177 parts on 4 layers; needs a manual fanout/placement pass or 6 layers, "
       "or the ISP1807/HJ-840 low-profile radio (MINIATURIZATION.md). The monolithic 185-part board `board/v010*` is the superseded reference (never routed) |")
open(p, "w").write(s[:i] + new + s[j:])
