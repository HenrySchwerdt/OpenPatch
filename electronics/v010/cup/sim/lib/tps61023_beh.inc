* TPS61023 BEHAVIOURAL (averaged) model.  NOT a TI model: written from the TPS61023 datasheet SLVSF14B because the vendor PSpice model
* (TI SLVMD68) does not run correctly in ngspice (see REPORT.md, section "Vendor models").
*
* What is modelled (datasheet numbers in brackets):
*   - UVLO with hysteresis: VIN rising 1.8 V, falling 0.4 V; EN high 1.2 V, EN low 0.42 V
*   - pre-charge of VOUT from VIN: 0.35 A below 0.4 V, ~1.0 A above (ILIM_CHG 0.75..1.2 A), until VOUT ~ VIN
*   - soft start: reference ramps 0 -> 0.595 V in tss (700 us total start-up at VIN 2.5 V, COUT 10 uF)
*   - regulation to VREF = 0.595 V at FB with a PI error amplifier (no ripple: averaged, no switching frequency)
*   - power balance: input power = output power / eta (conduction + switching loss lumped in eta, no separate DCR); SW pin = inductor side
*   - input current limit (valley limit 2.7..3.7 A -> ilimsw), OVP 5.7 V (stops delivering), true load disconnect when disabled
* Not modelled: switching ripple, PFM, pass-through, thermal shutdown, short-circuit foldback below 1.8 V.
* Pins as TPS61023: EN FB GND SW VIN VOUT. The external inductor goes VIN -> SW; the model sinks the input current from SW.
.subckt TPS61023_BEH en fb gnd sw vin vout params: eta=0.88 ilimsw=3.0 tss=700u vref=0.595 ichg=1.0 ichg0=0.35 ovp=5.7 kp=5 ki=2e5
Vone one gnd 1
Sen one enok en gnd swen
Rpd1 enok gnd 1k
Svi one vinok vin gnd swvin
Rpd2 vinok gnd 1k
.model swen sw vt=0.81 vh=0.39 ron=1 roff=1e9
.model swvin sw vt=1.1 vh=0.7 ron=1 roff=1e9
Bon on gnd V = (v(enok) > 0.5 && v(vinok) > 0.5) ? 1 : 0
* pre-charge / run state with memory (no chatter when VIN dips under the pre-charge inrush):
*   set when VOUT has reached VIN - 0.1 V; cleared when disabled or VOUT < 1.8 V (output short: datasheet 7.3.7)
Crun run gnd 1n
Brun gnd run I = (v(on) > 0.5 && v(vout) > v(vin) - 0.1) ? 1m * (1 - v(run)) : (((v(on) < 0.5) || (v(vout) < 1.8)) ? -1m * v(run) : 0)
Rrun run gnd 1e12
Bpc pc gnd V = v(on) * (1 - max(0, min(1, v(run))))
* soft-start reference: ramps while enabled, discharged when disabled
Css ss gnd 1n
Bss gnd ss I = v(on) * 1n * min(vref / tss, 2e4 * (vref - v(ss)))
Sres ss gnd offc gnd swres
Boff offc gnd V = (v(on) < 0.5) ? 1 : 0
.model swres sw vt=0.5 vh=0.1 ron=100 roff=1e12
* error amplifier: PI with smooth anti-windup, output = commanded current delivered into VOUT by the power stage
Bef e gnd V = v(ss) - v(fb)
Cint vint gnd 1u
Bint gnd vint I = ki * 1u * v(e) * (1 + 50 * (1 - tanh(v(e) * 50))) * (0.5 * (1 + tanh(v(e) * 50)) + 0.5 * (1 - tanh(v(e) * 50)) * 0.5 * (1 + tanh(v(vint) / 0.02)))
Sresi vint gnd offc gnd swres
Rint vint gnd 1e9
Bimax imax gnd V = ilimsw * eta * max(v(vin), 0.5) / max(v(vout), 1)
Bcmd icmd gnd V = v(on) * (1 - v(pc)) * 0.5 * (1 - tanh((v(vout) - ovp) / 0.02)) * max(0, min(v(imax), v(vint) + kp * v(e)))
* pre-charge current (linear, from VIN through the inductor path into VOUT)
Bchg ichgn gnd V = v(pc) * v(on) * (ichg0 + (ichg - ichg0) * max(0, min(1, (v(vout) - 0.4) / 0.3))) * max(0, min(1, (v(vin) - v(vout) + 0.1) / 0.3))
Bout gnd vout I = v(ichgn) + v(icmd)
Bin sw gnd I = v(ichgn) + v(icmd) * max(v(vout), 0.5) / (eta * max(v(vin), 0.5)) + v(on) * 20u
Csw sw gnd 50p
.ends TPS61023_BEH
