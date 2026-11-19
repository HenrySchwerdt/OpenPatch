# Fluid module from catalogue parts: research (2026-11-19)

Scope: OpenPatch test project, **water only, never on a person**. Question: can the reservoir-outlet fluid module (fill septum + one-way check valve + outlet needle + channels + seal to reservoir port) be assembled from orderable catalogue parts into a simple holder, inside 32 mm width, 8.4 mm total height (free height about 6 mm, fluid axis about 3 mm above the bottom, 6-10 mm length)?

Method and honesty note: WebSearch plus WebFetch only, run 2026-11-19. Search results were thin. Everything below is tagged **[V]** (seen on a fetched/search-result page, URL given) or **[U]** (unverified: from memory, inferred, or the page was not readable). No part numbers were invented; where a number is missing it says so. **Prices and private-buyer availability are mostly [U]**: they must be confirmed by asking the vendor before ordering. PDF datasheets from Lee (PDS159, PDS164) could not be machine-read, so their drawings (length, hole) are not verified.

## 1. Check valves

| Candidate | OD / length | Cracking | Back pressure | Materials | Price / availability | Verdict |
|---|---|---|---|---|---|---|
| Lee **CCPI 4.5 mm press-in** (CCPI4510004S = 0.6 ± 0.4 psid; CCPI4510007S = 1 ± 0.7 psid; 4510000S = no spring) | body OD **4.69 mm** [V, DirectIndustry]; length not found [U]; install hole about 4.54 ± 0.04 mm [U, read from vent-valve drawing text] | **4 ± 3 kPa (0.6 psid)** [V] | not found [U] | all stainless, 302 spring, 440C ball, metal-to-metal seat [V]; made to be pressed into plastic (not metal) [V] | price not found [U]; Lee sells via distributors, small-order route must be asked (sales 860-399-6281 per datasheet) | **Best technical fit**: fits 6 mm height, medical-capable. Metal seat is not zero-leak in reverse [U], fine for "no air sucked in" at bench level. Needs a reamed 4.54 mm hole in the holder. |
| Lee **5.5 mm CCPI (855 series, 316L, ceramic ball)** | 5.5 mm x 7.3 mm [V, secondary source] | not listed [U] | not listed | 316L, ceramic ball | price [U] | Bigger, still fits 6 mm. Fallback. |
| Lee **6.5 mm CCPI** (CCPI6510040S 6 psid ... 6510150S 21.8 psid) | 6.5 mm [V] | 6-22 psid [V] | n/a | SS | [U] | Too tall for 6 mm free height and cracking too high. Reject. |
| Lee **2.5 mm 316L press-in with ceramic ball** (PDS 208) | 2.5 mm [V title only] | not read [U] | | 316L, ceramic | [U] | Interesting for height, datasheet not read; ask Lee. |
| Lee **093 Lee Chek** (0.093" = 2.36 mm, 0.33" = 8.4 mm long) | 2.36 x 8.4 mm [V] | **5 ± 3 psid** [V] | n/a (system up to 4000 psi) | 15-5PH SS, 440C ball | needs Lee insert tooling CUTA0930106C [V] | Too high cracking, needs special install tool. Reject. |
| Lee Zero-Leak 0.250" | 6.35 mm [V] | 5 ± 3 psid [V] | | elastomer seat | [U] | Too tall/high cracking. |
| **Beswick CKV-M3 duckbill**, 5 mm hex body | hex 5 mm, no length given [V] | "typically < 0.5 psig" [V] | housing 250 psig; barbed 100 psig [V] | brass or 303 SS body, duckbill element [V] | price not shown, sold direct in USA [V]; EU route unknown [U] | Right function (duckbill, low crack, tiny), metal body (not medical grade, ok for water). Ask for a sample/EU distributor. |
| **Qosina 80105** inline check valve | OD 3.3-3.5 mm at both tubing ports [V] | **1.5-5 psi** [V] | not stated | acrylic housing + silicone diaphragm [V] | $2.56 each, currently "incoming stock" [V]; Qosina Europe exists (qosina.com/qosina-europe) but is B2B, expect minimum order or sample workaround [U] | Medical-component family, cheap, but the 3.4 mm tubing ports need about 3 mm ID tubing: large dead volume for a 0.3-0.5 mm channel. Length not found [U]. |
| Qosina 91052 high-flow | not read | 0.029 psi [V] | | acrylic + silicone | [U] | Very low crack but bigger. |
| IDEX/Upchurch **CV-3000/3001** inline cartridge | cartridge OD/length unclear (1.04"/1.92" snippet) [U] | 1.5 ± 0.5 psi [V] | 1000 psi [V] | PEEK, perfluoroelastomer seals, gold SS spring [V] | sold via biotechfluidics / chromtech / frisenette.dk [V] | Housing is 1/4-28 port + 1/16" tube fittings: too long (> 25 mm) for 6-10 mm. Reject. |
| Minivalve International connector valve (3 mm / 1/8" slip fit, silicone) | 3 mm [V] | not found | | silicone | info@minivalve.com [V], small-lot price unknown [U] | Medical-grade manufacturer, EU (NL). Ask for samples: possibly the best long-term (manufacturer) route. |
| Marketplace silicone duckbill inline 3.2 / 4.0 / 4.8 mm (eBay.de, Alibaba) | 3.2-4.8 mm [V, snippet] | not stated [U] | 300 kPa claimed [V] | white silicone, RoHS only [V] | about 1 EUR, "small orders accepted" [V] | Cheapest, unvalidated; must be bench-tested (crack, reverse leak). OK for a first prototype only. |
| Cole-Parmer/Masterflex PP mini check valves | 1/8", 3/16", 1/4" barbs [V] | 0.18 psi break [V] | needs ~1 psi back pressure to seal [V] | PP + Viton | fishersci | Too big. Reject. |

Reading: in the whole search **no catalogue valve is a tiny medical duckbill with 0.3-0.5 mm ports**. Everything available is either a 3-5 mm cartridge (Lee, Beswick) or has tubing ports of about 3 mm. So the valve is the module's largest part and the holder is designed around a 4.5-5 mm bore, 7-9 mm long, in the 6 mm free height (fits: 4.69 mm OD leaves 1.3 mm for walls, tight; the CCPI axis at 3 mm above bottom means the bore reaches 3 + 2.35 = 5.35 mm, leaving about 1.5 mm above if the lid is at 8.4 mm minus 0.9 mm = 7.5 mm).

## 2. Septum / fill ports

| Candidate | Size | Notes |
|---|---|---|
| PTFE/silicone HPLC/GC vial septa, e.g. 11 mm x 0.075" (1.9 mm) for 4 mL vials [V, Sigma-Aldrich], Agilent 13-425 red PTFE/silicone [V], MZ Analysentechnik (Germany) sells vial septa [V mz-at.de] | 11 mm discs; thickness 0.25-4 mm [V] | Cheap (about 10-30 EUR per 100 [U]), sold in Germany to private persons via lab shops [U]. Punch a 4 mm disc with a hollow punch or use the 11 mm disc whole. PTFE face must face outwards; pure silicone septa exist [V]. |
| Pre-slit septa, 4 mm | not found [V] | no private-buyer source found |
| Qosina swabbable needleless injection sites (e.g. 80228) | smallest port found 4.1 mm; body far longer than 10 mm (Luer) [V] | Too long. Reject. |
| IDEX/VICI/Cheminert septum injection port | not found [U] | 1/4-28 hardware, too large. |
| MiniMed reservoir silicone membrane [V] | dimension not found | Only available with the whole reservoir. |

Conclusion: no catalogue "septum port" fits 6 mm height. Best simple solution: a punched silicone or PTFE/silicone septum clamped by a printed ring/screw (the holder only needs to compress it axially, no tight molded fit needed). This is the only soft part left, but it is a flat disc, not a molded insert.

## 3. Outlet needle / tubing

- 30G blunt needles with Luer hub exist: CELLINK sterile blunt 30G x 0.25" (6.35 mm), PP hub, 50 per box [V]; McMaster sells blunt Luer dispensing needles (US, not EU shop) [V]; B. Braun 30G (0.30 x 12 mm), origin Germany, but sharp (injection needle) [V]. **No hub-less 30G blunt needle found** [V]. Workaround: cut the needle off the hub (side cutter, then deburr) and glue it into the holder with epoxy/UV glue, or keep the Luer hub and make the holder a female-Luer-slip boss (hub is too tall for 6 mm: not workable).
- The existing design stays: a 30G needle (0.31 mm OD) piercing the cannula septum; blunt vs sharp is a safety/design decision for the owner.
- Microtubing: not researched to part number; IDEX 1/16" PEEK/PTFE tubing ID 0.25-0.5 mm is the standard route [U]. No micro-ferrule fitting small enough for 6-10 mm length was found; 10-32 fittings are about 10 mm long and 8 mm OD hex [U].

## 4. Integrated modules

Nothing found that combines septum + one-way valve + needle in a pod-sized part. Specifically:
- Needle-free connectors (Qosina, Nordson Halkey-Roberts) are Luer-sized (> 15 mm long) [V].
- Pen cartridge crimp cap + septum, pen needle: not purchasable separately in small quantity [U].
- Ink-jet CISS valves, vape cartridge valves, perfume atomiser valves: not found in results; typically 5-15 mm, non-medical [U]. Not pursued further.
- MiniMed reservoir already integrates plunger, membrane and Luer-style connector, but is not sold as a bare part to private persons in a usable way and dimensions were not found [V availability via many diabetes shops, EUR per piece [U]].

## 5. Alternative reservoir (cartridges)

| Cartridge | Dimensions | Fits 8.4 mm height? |
|---|---|---|
| 3 mL insulin pen cartridge (ISO 13926-1) | OD about 9.25-11.6 mm depending on source (conflicting: supplier list says 11.6 mm; my memory says about 11.5) [V conflicting, U] | No (> 6.6 mm) |
| 1.8 mL dental cartridge (ISO 11040-1) | supplier list: OD 8.65 mm x 63 mm [V, Made-in-China listing]; standard says 8.2-ish [U] | No: 8.65 mm + wall > 8.4 mm |
| 1.0 mL dental (ISO 11499) | exists [V]; dimensions not found [U] (about 6.85 mm bore from memory, **unverified**) | Possibly, marginal; I could not find a source |
| MiniMed MMT-326A 1.8 mL | dimensions not found [V] | unknown, ask for/measure a sample |

So **no verified standard cartridge fits the 5.6 mm bore / 6.6 mm OD limit**. A 1.0 mL ISO 11499 cartridge is the only one worth checking (its Ø would need to be at most 6.6 mm), but it has no source and would also need a lead screw geometry change. A cartridge would replace septum + reservoir (crimp cap septum on the outlet end, outlet needle pierces it: this is how dental/pen cartridges work), but the 1.8 and 3 mL types are too thick. Marked as a research dead end unless the owner accepts taller or 2-column layout.

## Ranked recommendation

**1. Lee CCPI 4.5 mm (CCPI4510004S, 0.6 psid) + punched septum disc + cut 30G needle. Best match, medical-capable.**
- Check valve: Lee CCPI4510004S, OD 4.69 mm, SS, 0.6 psid [V]. Seals by press fit in plastic (ream a 4.54 mm hole in the holder) [V press-in; hole [U]]. Price/private availability: ask Lee distributors; unverified.
- Fill septum: punched 4 mm disc of PTFE/silicone or silicone septum (lab shop, mz-at.de [V]); clamped by a printed ring.
- Outlet: 30G needle cut off a hub, epoxy/UV glue (need blunt version, CELLINK [V]).
- Holder: bore 4.54 mm reamed (or printed 4.4 mm and reamed), septum seat 4 mm, needle bore 0.35 mm channel, port boss to the reservoir port with a small O-ring or glue, flow path reservoir port -> valve -> tee -> needle; septum on the reservoir side of the valve (fill), so the valve only needs to open for delivery. Open question: the draw-mode concept in the design (refill by retracting through the septum) needs septum on the reservoir side of the valve; check valve then blocks air via the needle. Cost unknown [U].

**2. Beswick CKV-M3 (5 mm hex duckbill, < 0.5 psig) as the valve, same septum + needle.** Truer "duckbill" function, but needs a US vendor, metal body, 5 mm hex needs a hex pocket and about 1 mm more height; EU purchase [U]. Good if Lee refuses small orders.

**3. Cheapest first prototype: marketplace silicone duckbill 3.2/4.0 mm [V snippet] or Qosina 80105 (3.4 mm OD ports, $2.56, 1.5-5 psi [V])** in a 3.4 mm holder bore with silicone tube stubs, plus septum disc and cut needle. Cracking pressure of 1.5-5 psi for Qosina is relatively high; marketplace valves unspecified and not medical-grade. For a future manufacturer, ask Minivalve International for a molded silicone duckbill (EU, the closest to a mass-produced route).

Cartridges (section 5) are **not recommended** (no verified size under 6.6 mm).

## What the printed holder must still do
1. Locate the valve bore (4.54 mm press-in for CCPI) and give it a 0.5 mm flow channel to the needle and septum pocket.
2. Compress the septum disc axially (ring + one screw) so it stays leak-tight with the fill needle in place.
3. Hold the needle (glued) and the cannula-side guide; seal to the reservoir port (O-ring or solvent/epoxy).
4. Keep every wetted channel dead volume small and vent/prime path accessible (valve + septum add about 10-60 uL [U]).
5. Remain within height 8.4 mm: this leaves about 1.3-1.5 mm total wall around a 4.69 mm valve [calculation, tight].

## Open items needing a human with a phone or a mailbox
- Ask Lee for price, minimum order, length of CCPI4510004S and the PDS 208 (2.5 mm) cracking pressure.
- Ask Beswick/Minivalve for samples.
- Measure actual cracking and reverse leak of whichever valve is bought.

## Sources (accessed 2026-11-19)
- https://www.theleeco.com/uploads/2021/11/PDS159-2017-5-IMH4.5mmCCPI.pdf (PDF not machine-readable)
- https://theleeco.com/product/4-5-mm-press-in-check-valve
- https://www.theleeco.com/uploads/2021/11/PDS164-2017-7-IMH6.5mmCCPI.pdf
- https://www.theleeco.com/product/093-side-exit/
- https://www.directindustry.com/prod/the-lee-company/product-5322-2803802.html
- https://www.beswick.com/catalog/product-detail/CKV-M3
- https://www.qosina.com/check-valve-white-inlet-clear-outlet-80105
- https://www.qosina.com/high-flow-check-valve-tubing-port-inlet-tubing-port-outlet-91052
- https://www.idex-hs.com/store/product-detail/check_valve_inline_cartridge_1_5_psi
- https://minivalve.com/?p=4340
- https://www.ebay.de/itm/187583244426 (marketplace duckbill)
- https://www.mz-at.de/en/products/vials/vial-septa.html
- https://b2b.sigmaaldrich.com/IN/en/substance/septawhiteptfesilicone1234598765
- https://www.galaxus.de/en/s6/product/bbraun-needle-30g-medical-supplies-equipment-21423205
- https://www.mcmaster.com/products/needles/needle-gauge~30-ga/
- https://cosmepkg.en.made-in-china.com/product/lFwAHYhvhpaf/China-3ml-Clear-Glass-Cartridge-with-Needles-and-Pens.html
- https://www.iso.org/standard/67064.html (ISO 11040-1 scope)
- https://www.diabetes.shop/reservoirs/18reservoir/mmt-326a
