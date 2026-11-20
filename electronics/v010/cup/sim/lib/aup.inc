* Behavioural 74AUP1Gxx gates and D flip-flop with async clear (TP74AUP1G00/G08 = AUP1G00/G08 compatible, SN74AUP1G74).  NOT vendor models.
* Datasheet numbers used: VCC 0.8..3.6 V, logic threshold taken as 0.5 VCC (datasheet VIH 0.65 VCC / VIL 0.35 VCC: a floating input is NOT modelled
* as a defined level; it is a node with only 1 pF to ground, so its level is whatever the test sets by .ic or by leakage = undefined),
* output resistance ~25 ohm (AUP at 3.3 V), supply current ~ 0.
* Below VCC = 0.8 V the output is UNDEFINED. Parameter undef (0..1) sets the worst case: output = undef * VCC (1 = follows the rail, i.e. "looks high").
.subckt aup_and2 a b y vcc gnd params: undef=1
Bg yt gnd V = (v(vcc,gnd) > 0.8) ? (((v(a,gnd) > 0.5 * v(vcc,gnd)) && (v(b,gnd) > 0.5 * v(vcc,gnd))) ? v(vcc,gnd) : 0) : undef * v(vcc,gnd)
Ry yt y 25
Cy y gnd 1p
Ca a gnd 1p
Cb b gnd 1p
.ends aup_and2

.subckt aup_nand2 a b y vcc gnd params: undef=1
Bg yt gnd V = (v(vcc,gnd) > 0.8) ? (((v(a,gnd) > 0.5 * v(vcc,gnd)) && (v(b,gnd) > 0.5 * v(vcc,gnd))) ? 0 : v(vcc,gnd)) : undef * v(vcc,gnd)
Ry yt y 25
Cy y gnd 1p
Ca a gnd 1p
Cb b gnd 1p
.ends aup_nand2

* SN74AUP1G74: Q after a rising CLK edge = D, async CLR (active low) dominates, PRE tied high (not modelled).
* Master-slave built from switches and capacitors; the charge leaks away through gmin (tau ~ 10 s), as a real unpowered flop loses its state.
.subckt aup74 clk d q clrn vcc gnd
Bml ml gnd V = (v(clk,gnd) < 0.5 * v(vcc,gnd)) ? v(vcc,gnd) : 0
Bsl sl gnd V = (v(clk,gnd) > 0.5 * v(vcc,gnd)) ? v(vcc,gnd) : 0
Bcl cl gnd V = (v(clrn,gnd) < 0.5 * v(vcc,gnd)) ? v(vcc,gnd) : 0
Sm d m ml gnd swf
Cm m gnd 5p
Bmb mb gnd V = v(m,gnd)
Ss mb s sl gnd swf
Cs s gnd 5p
Sc1 s gnd cl gnd swc
Sc2 m gnd cl gnd swc
.model swf sw vt=0.4 vh=0.05 ron=100 roff=1e13
.model swc sw vt=0.4 vh=0.05 ron=10 roff=1e13
Bq qt gnd V = v(s,gnd)
Rq qt q 25
Cq q gnd 1p
Cc clk gnd 1p
Cd d gnd 1p
Ccl clrn gnd 1p
.ends aup74
