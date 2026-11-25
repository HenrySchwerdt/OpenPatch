> **TEST ONLY - NOT FOR HUMAN USE** (see `../DISCLAIMER.md`). Bench only, **water only**: no cartridge in this project is ever filled with insulin or any other drug, and nothing here is an instruction for use on a person.

# Accu-Chek Insight system: public facts for the "cart" pump (research 2026-11-24)

Purpose: mechanical reverse engineering for `mechanical/V010-CART.md` (a small bench pump around an Insight-class 1.6 ml cartridge and the original Insight adapter & tubing).
**VERIFIED** = read on the cited page or PDF in this session. **ESTIMATE** = derived, from a search excerpt, or not stated by the manufacturer.
**No dimensional drawing of the cartridge, the stopper or the adapter is public.** Every cartridge and adapter number in the CAD is therefore an ESTIMATE until measured on a bought sample (list at the end).

## Sources
| Key | Document | URL |
|---|---|---|
| M | Accu-Chek Insight insulin pump User's Manual, Appendix A, doc 06719414001/M (2020-12, UK) | https://www.accu-chek.co.uk/document/accu-chek-insight-insulin-pump-users-manual/download |
| A | Accu-Chek Insight Adapter & Tubing instructions for use, 00048011809/F (2020-09) | https://www.accu-chek.co.uk/document/accu-chek-insight-adapter-tubing-instructions-use/download |
| H | Roche DE handling sheet "Wechsel der Ampulle" | https://www.accu-chek.de/document/accu-chek-insight-handhabungshinweise-wechsel-der-ampulle/download |
| V | Roche DE pump version overview (2018) | https://www.accu-chek.de/document/accu-chek-insight-versionsuebersicht/download |
| P | Roche DE price list, valid from 2026-09-01 | https://a.storyblok.com/f/94122/x/ab450b3a24/preisliste-diabetes-care-09-2026_rdd.pdf |
| S | NovoRapid PumpCart SmPC (UK eMC), section 6.5 / 6.6 | https://www.medicines.org.uk/emc/product/7922/smpc/print |
| F | Accu-Chek Insight Flex instructions for use, 00048011468/F (2019-04) | https://www.accu-chek.co.uk/document/accu-chek-insight-flex-instructions-use/download |
| T | Swedish TLV decision 602/2015 (Insight adapter) | https://www.tlv.se/download/18.467926b615d084471ac30c8b/1510316369255/bes150604-accu-chek-insight-adapter.pdf |
| O | Omnipod comparison chart (Insulet, CA) | https://www.omnipod.com/sites/default/files/CAN_Omnipod%20Comparison%20Chart%20Updates_ENG_1.pdf |
| Y | mylife YpsoPump / YpsoPump Reservoir product pages | https://www.mylife-diabetescare.com/en/products/infusion-systems/mylife-ypsopump-reservoir.html |

## 1. Pump outer dimensions and weight
| Item | Value | Status | Src |
|---|---|---|---|
| Insight maximum dimensions **with adapter** | approx. **84 x 52 x 19 mm** | VERIFIED | M p.98 |
| Weight, empty pump | approx. 99 g | VERIFIED | M p.98 |
| Weight with cartridge, battery and infusion set | approx. 122 g | VERIFIED | M p.98 |
| Battery | 1 x AAA 1.5 V (LR03 alkaline or FR03 lithium, >= 1200 mAh) | VERIFIED | M p.98 |
| Battery life | lithium >= 20-21 d, alkaline >= 5-6 d | VERIFIED | M p.99 |
| Cartridge | 1.6 ml = 160 U (the only type listed) | VERIFIED | M p.100-101 |
| Occlusion alarm threshold / maximum pressure | <= 330 kPa / 350 kPa | VERIFIED | M p.100 |
| Volume before occlusion message | <= 2.0 U (20 ul) | VERIFIED | M p.100 |
| Adapter vent minimum opening pressure | 0.65 bar | VERIFIED | M p.100 |
| Max. delivered under a single fault | <= 0.8 U | VERIFIED | M p.101 |
| Water rating | IPX8 (1.3 m, 60 min); the adapter itself is not watertight | VERIFIED | M p.101 |
| FDA 510(k) | none found (Insight apparently never US-cleared) | ESTIMATE | accessdata.fda.gov search |
| Omnipod DASH / Omnipod 5 pod | 52 x 39 x 14.5 mm, 200 U, about 25-26 g without insulin | VERIFIED (chart values) | O |
| mylife YpsoPump (same 1.6 ml cartridge class) | 78 x 46 x 16 mm | ESTIMATE (search excerpt of the mylife page) | Y |

## 2. Drive principle
| Item | Finding | Status | Src |
|---|---|---|---|
| Motor | "brushless motor", safety component | VERIFIED | M p.101 |
| Control | two microprocessors plus a supervisor processor; motor switched off on overdelivery (E7) | VERIFIED | M p.101 |
| Piston rod | "piston rod" (EN manual) / "threaded rod" (German handling sheet); rewinds automatically at each cartridge change | VERIFIED | M p.27, H |
| Rod to stopper | the cartridge goes in stopper first; after the adapter is locked the pump "detects the position of the plunger" (sensing method not public) | VERIFIED behaviour | A step 4 |
| Telescopic rod, gear ratio, lead, encoder, occlusion sensing method | not public; no teardown found | must be measured / unknown | - |

## 3. Cartridge system
| Item | Value | Status | Src |
|---|---|---|---|
| Prefilled PumpCart content | 1.6 ml (160 U at 100 U/ml) | VERIFIED | S 6.5 |
| Barrel material | type 1 glass (not a polymer) | VERIFIED | S 6.5 |
| Stopper (plunger) | bromobutyl rubber | VERIFIED | S 6.5 |
| Closure (septum) | bromobutyl / polyisoprene rubber, crimp cap | VERIFIED | S 6.5 |
| Pack, refill | 5 cartridges per pack; must not be refilled | VERIFIED | S 6.5-6.6 |
| Compatible pumps | Accu-Chek Insight and YpsoPump | VERIFIED | S 6.6 |
| Label feature | white band at the plunger end; the stopper must not be past it | VERIFIED | H |
| Empty self-fill Insight cartridge | offered in pump versions 1.0-2.1 ("prefilled / self-filled"); version 3.0 (Dec 2018) shows only "1.6 ml" | VERIFIED table; ESTIMATE that self-fill was discontinued | V |
| **OD, length, ID, stopper size, neck, crimp cap, wall** | **not published** by Roche or Novo Nordisk | **must measure** | - |
| CAD values (since 2026-11-24, see §7) | ISO 13926-1 1.6 ml row: OD 10.95, ID 9.25; neck 5.5, collar 7.15, h1 5.0; cap 7.8 x 3.2, barrel 33.5, stopper 9.25 x 6.5 | ISO rows VERIFIED, mapping to the Insight cartridge ESTIMATE | `params.json -> cart.cartridge` |

**Empty cartridges for the bench:** no current Roche REF/PZN for an empty Insight cartridge was found (price list P, UK order page). The practical bench source is the **mylife YpsoPump Reservoir 1.6 ml** (empty glass self-fill cartridge of the same 1.6 ml class, PZN 11160770, 10 per pack, about 50-61 EUR: ESTIMATE from search excerpts). Whether it fits and seals with the Insight adapter is **UNVERIFIED**. Do not buy NovoRapid PumpCart: it is a prescription drug and this project is water only.

## 4. Insight adapter & tubing (the part the cart pump keeps)
| Item | Finding | Status | Src |
|---|---|---|---|
| Parts | adapter with a needle in the centre of its "nose"; tubing integrated (no separate adapter part) | VERIFIED | A, T |
| Septum piercing | the needle must meet the cartridge centrally and perpendicularly; the nose enters the housing notches at 90 deg, otherwise the needle can bend | VERIFIED | A step 1 |
| Lock | placed on the **bayonet socket** of the cartridge compartment, turned clockwise to a stop until flush with the housing; figures show 90 deg and 120 deg positions, removal about 120 deg anticlockwise | VERIFIED | A, M p.27-29 |
| Vent | adapter vent, minimum opening pressure 0.65 bar | VERIFIED | M p.100 |
| Sealing to the cartridge | not public (probably needle through the septum + axial preload of the cap by the bayonet) | ESTIMATE | - |
| Change interval | new adapter with every cartridge | VERIFIED | A, T |
| REF / PZN | 40 cm 06485472001 / 08460327; 70 cm 06485499001 / 15379353; 100 cm 06485464001 / 08460356; 10 per box, 37.50 EUR list / 48.45 EUR RRP | VERIFIED | P p.17 |
| Field safety notice 2022 | some adapter & tubing lots leaked and were recalled | VERIFIED (title/summary) | https://laegemiddelstyrelsen.dk/da/udstyr/sikkerhedsmeddelelser/2022/05/~/media/0284DC5BFA8C42B1B384B5CF508BCD7B.ashx |
| Nose OD, lug count / size / axial position, rotation angle, needle OD / length, cap preload | not public | must measure | - |

## 5. Insight Flex head set (far end of the tubing)
| Item | Value | Status | Src |
|---|---|---|---|
| Cannula lengths | 6 / 8 / 10 mm | VERIFIED | F |
| Head set fill volume | 0.7 U (about 7 ul) | VERIFIED | F |
| Tubing fill volume | 40 / 70 / 100 cm -> 9 / 13 / 17 U (90 / 130 / 170 ul); a UK chart says 7 / 11 / 15 U | VERIFIED (F), conflicting chart | F |
| Connector | "connector plate" on the head set, released by squeezing side clips | VERIFIED | F |
| PZN (10 head sets, 6 / 8 / 10 mm) | 08459755 / 08459761 / 08459778, 80.10 EUR list | VERIFIED | P p.17 |
| Connector geometry | not public (see `mechanical/cannula-measurement.md`) | must measure | - |
For the cart pump bench the tubing ends in a container on a scale (water only); a head set is optional.

## 6. Patents to respect (Google Patents estimates; not legal advice)
| Number | Title / owner | Priority | Status / expiry | Relevance |
|---|---|---|---|---|
| US9554967B2 (EP2712650A1) | Adapter and drug cartridge alignment device, Roche | 2012-09-27 | listed "Expired - Fee Related" (adj. 2034-10-25) | cartridge-to-adapter alignment structures, bayonet coupling to the pump, vent membrane: the closest match to Insight. We use the **original** adapter and cartridge and copy no adapter geometry; our receiver is a generic two-lug bayonet socket |
| US20140221930A1 | Venting device for ambulatory infusion system, Roche | 2012-09-27 | abandoned | hydrophobic vent at the stopper side, pusher plate piercing it |
| **US9205190B2** | Modular infusion pump, Disetronic -> Roche | 2003-06-17 | **active**, adj. expiry 2029-08-10 | motor + gear wheel threaded onto a threaded piston rod pushing the stopper: **the same drive principle as the cart pump** (gear nut + translating rod). Claim 1 not read in full: check it before publishing or distributing hardware; a bench experiment is a different matter from a product, get legal advice |
| US9427519B2 (EP2192935B1) | Cartridge adapter for infusion system, Roche | 2007-10-01 | active, adj. 2028-10-17 | monolithic snap-in adapter with a septum cannula; not a bayonet, not used here |
| US7806868 | Reservoir loading mechanism with unidirectional rotated shaft, Roche/Disetronic | before 2010 | not checked | piston rod with a flexible nut segment; title and dates from a search excerpt only (ESTIMATE) |
Expiry dates are Google Patents estimates, not legal conclusions. No Insight-specific drive patent with a brushless-motor claim was found.

## Must measure on a sample (before the cart CAD is frozen)
1. Cartridge (empty YpsoPump Reservoir, or an emptied Insight cartridge, rinsed): OD, overall length, glass ID (ul per mm of stroke), neck and crimp-cap OD and height, septum free diameter, any rear-end flange or chamfer.
2. Stopper: OD, length, position when full (distance from the rear end), maximum travel to the shoulder; breakaway and glide force dry and with water (the thrust budget assumes 8 N, `cart_check.py`).
3. Adapter: nose OD and insertion depth, lug count / width / height / axial position, rotation angle to the stop (90 or 120 deg), needle OD, length and protrusion past the nose, axial preload on the cap, vent location; vent cracking pressure (spec >= 0.65 bar).
4. Whether the YpsoPump Reservoir and the Insight adapter fit and seal together (water, 1 bar hold, 10 min).
5. Tubing ID / OD and the dead volume of 40 cm (expected 90 ul).
Enter the values in `mechanical/params.json -> cart.cartridge / cart.adapter / cart.receiver`, then `python3 cart_gen.py && python3 cart_check.py`.

## Buying (empty fluid-path parts only, used with water)
| Item | REF / PZN | Shop | Price | Note |
|---|---|---|---|---|
| Accu-Chek Insight Adapter & Tubing 40 cm, 10 pcs | 06485472001 / 08460327 | German pharmacy by PZN, or https://www.ebay.de/itm/136429243755 | 37.50 EUR list / 48.45 EUR RRP (P) | shortest dead volume; avoid the 2022 recall lots |
| Accu-Chek Insight Adapter & Tubing 70 cm (alternative) | 06485499001 / 15379353 | https://www.docmorris.de/accuchek-insight-adapter-schlauch-70-cm/15379353 | 48.45 EUR RRP | |
| mylife YpsoPump Reservoir 1.6 ml, 10 pcs (empty glass) | PZN 11160770 | https://www.docmorris.de/mylife-ypsopump-reservoir/11160770 | about 50-61 EUR (ESTIMATE) | fit with the Insight adapter UNVERIFIED |
| Insight Flex head sets 6 mm (optional) | PZN 08459755 | https://www.docmorris.de/accu-chek-insight-flex-6-mm/08459755 | 80.10 EUR list | only for a connector fit test; not needed for the container bench |

## 7. Update 2026-11-24 (second research pass): cartridge standard, adapter internals, Flex / FlexLink, variant B

### 7.1 The cartridge is an ISO 13926-1 pen cartridge format
SCHOTT TopLine (https://media.schott.com/api/public/content/52830d43591e4e929f12dfc14687786a) and StandardLine (https://media.schott.com/api/public/content/79cef30f8ec1439da113d780a4a059bc) cartridge sheets, "formats according to pen ISO 13926-1", crimp neck finish (table read, VERIFIED):
| Parameter | 1.5 ml ISO | **1.6 ml ISO** | 3.0 ml ISO (Penfill class) | 3.0 ml slim |
|---|---|---|---|---|
| barrel OD d1 | 8.65 | **10.95** | 11.6 | 10.85 +-0.1 |
| barrel ID d2 | 6.85 | **9.25** | 9.7 | 8.65 +-0.09 |
| d3 min | 6.55 | 8.95 | 9.35 | 8.35 |
Neck, shared by all ISO rows 8.65-11.6 OD (VERIFIED): collar d4 **7.15 +-0.2**, neck d5 **5.5 +-0.25**, neck bore d6 3.15 +-0.2, neck + collar h1 **5.0 +-0.2**, collar h2 **2.9 +-0.1**; overall length "agreed between manufacturer and customer" (drawing range 35-120).
Crimp cap axial length "typically 2 mm to 3 mm" and cartridge volumes "about 1.5 ml or about 3 ml" (US9554967B2 text, VERIFIED). ISO 13926-1:2026 itself is paywalled (https://www.iso.org/standard/89250.html).
**So the owner is right that it is a standard format with a standard neck.** Which row: the 1.6 ml ISO row (OD 10.95 / ID 9.25) is the best match by name and volume, but no source ties the PumpCart / YpsoPump Reservoir to it: ESTIMATE until measured (bracket 10.85-11.6 -> the fit coupon prints a bore ladder 11.0-11.8). With ID 9.25: 67.2 ul per mm, 1.6 ml = 23.8 mm stroke. Overall length incl. cap about 38-41 mm (derived: stopper 6.5 + stroke + shoulder + neck), ESTIMATE.

### 7.2 How the Insight adapter attaches, pierces, seals and locks (US9554967B2 embodiment + IFU)
| Item | Finding | Status |
|---|---|---|
| Coupling | bayonet into the cartridge-compartment socket; nose into the housing notches at 90 deg; clockwise to the stop (90 / 120 deg marks), flush with the housing; removal anticlockwise | VERIFIED (IFU A) |
| Piercing | needle in the centre of the nose; must meet the septum centrally and perpendicularly, else it bends | VERIFIED (IFU A) |
| Sealing / preload | O-ring 230 presses on the crimp cap and loads the cartridge axially; O-ring 235 seals the adapter to the housing; optional O-ring 240 separates septum and vent | VERIFIED as a patent embodiment (https://patents.google.com/patent/US9554967B2/en) |
| Vent | hydrophobic ring membrane on the cap face, vent channel 220 bypasses the O-rings | VERIFIED as an embodiment |
| Keying / anti-rotation | ribs on the cap / alignment part engage the adapter guide 215; alignment members 3 x 120 deg or 4 x 90 deg | VERIFIED as an embodiment |
| Lug count, lug size, needle gauge, any dimension | not stated anywhere | MEASURE |
Envelope ESTIMATE (used in the CAD): nose d12.4 x 5.5 (it must pass a cartridge of about 11 mm through the same opening), 2 lugs 1.6 x 0.8, body d14, about 6.5-12 outside the housing (84 - 72).

### 7.3 Insight Flex at the site end, FlexLink with Luer
| Item | Value | Status |
|---|---|---|
| Insight Flex head sets without tubing | PZN 08459755 / 08459761 / 08459778 (6 / 8 / 10 mm), 10 pcs, 80.10 EUR list | VERIFIED (price list P) |
| Tubings that fit the Insight Flex head | all Insight Adapter & Tubing (Flex, Tender, Rapid share one coupling) | VERIFIED (TLV 602/2015) |
| Tubing ID | about 0.41 mm (from 40 ul per 30 cm); OD not published (about 1.6-1.8) | ESTIMATE |
| Accu-Chek FlexLink (Combo) | head set + transfer set with a **Luer-lock connector (J) at the pump end**, side-wing connector at the site end; 8/30 PZN 01022469, 6/30 09517087, 10/30 01022506, 10 heads + 10 tubings, 117.60 EUR list / 152.10 RRP | VERIFIED (FlexLink IFU https://www.accu-chek.co.uk/document/accu-chek-flexlink-instructions-use/download, price list P) |
| FlexLink head == Insight Flex head? | **UNVERIFIED**: DE lists FlexLink with LinkAssist, Insight Flex with LinkAssist Plus (different heads?); a UK chart pairs "FlexLink Plus / Insight Flex" (probably the same head, ESTIMATE); FlexLink Plus is not in the DE price list | open |

### 7.4 Variant B (Insight cartridge + cheapest established alternative to the Insight adapter)
* **mylife YpsoPump Orbit sets**: the YpsoPump uses the same 1.6 ml cartridge class (IFU: self-filled 1.6 ml reservoir or NovoRapid PumpCart; https://a.storyblok.com/f/287658439214273/x/7a73cd2966/ypu_eifu_ref_700009424_uk-en_v02.pdf, VERIFIED); its Orbit adaptor sits on the cartridge and turns clockwise to a click / stop in the **YpsoPump housing** (geometry not public), site end = Orbit 360 deg base (not Insight Flex), 110-155 EUR per box (medpex / DocMorris excerpts). Rejected: proprietary on both ends, dearer.
* **Cartridge-to-Luer adapters**: no established commercial product found (InsuJet's cartridge adaptor fits only its own system).
* **Chosen B chain**: our printed bayonet cap centres a standard Luer-lock hypodermic needle (27G 0.40 x 12 mm, female Luer hub) on the septum axis and preloads the crimp cap like O-ring 230 -> the hub takes the Luer-lock pump end of an **Accu-Chek FlexLink** transfer set -> FlexLink head (or, if 7.3 is confirmed on the bench, an Insight Flex head). Gender check: the hypodermic hub is female; if the FlexLink pump end is also female, add a male-male Luer-lock coupler (lab part).
* Bench only, into a container, water only.

### 7.5 Adapter shape (correction 2026-11-24, owner's product photo + manual renders)
The Insight Adapter & Tubing is **not a round cap**. It is a flat, elongated, domed black body; the tubing leaves one narrow end; under the other end is a short connector cylinder (with a key / lug) that enters the cartridge compartment. In the user manual (p.28 step 8 and the "CORRECT" figure) and the adapter IFU (steps 1-2): the cartridge is inserted into the **end face** of the pump, the adapter is placed with its long axis **at 90 deg** to the housing, the connector nose goes into the notches, and the adapter is turned clockwise to the stop (90 / 120 deg marks) until the body lies **flush along the end face**.
Envelope scaled from the manual renders (pump face 52 mm, edge 19 mm as the scale; perspective, so ESTIMATE): body length 36 (face view) to 48 (edge view) -> **40 +-6**, width about 12, height 9-10 (dome); connector cylinder d10-12.5, protruding about 5, centre about 11 from the connector-side end. Insight 84 mm "with adapter" = body about 74-75 + adapter about 9-10.
CAD (variant A) since 2026-11-24: end face 40 mm wide, adapter bed 1.0 deep, connector port as before. All values to be measured on the bought adapter.

### 7.6 Adapter and end-face interface: thorough pass (2026-11-24, supersedes the 7.2 envelope and the 7.5 size estimate)
**Sources read as images** (none committed; the drawings are copyright Roche, link only):
- **US D720,449 S "Pump adapter"** (Roche, filed 2012-02-03, CH priority 2011-08-03), 8 views: perspectives https://patentimages.storage.googleapis.com/ee/eb/a1/88a58976d648e7/USD0720449-20141230-D00001.png, side views https://patentimages.storage.googleapis.com/45/db/5c/95a6aa64841511/USD0720449-20141230-D00002.png, bottom / top https://patentimages.storage.googleapis.com/3f/76/e5/d459f60cd16b9d/USD0720449-20141230-D00003.png, end views https://patentimages.storage.googleapis.com/e7/34/db/44a92d5217e1da/USD0720449-20141230-D00004.png, PDF https://patentimages.storage.googleapis.com/12/01/6e/eedfd368d68b45/USD720449.pdf
- **US D689,523 S "Infusion pump device"** (same filing), Fig. 6 = pump end face with the end cap (adapter) removed: https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/D689523
- US9554967B2 Figs 3 / 4b (cannula 210, channel 212, O-rings 230 / 235 / 240, vent 220, guide 215): https://patents.google.com/patent/US9554967B2/en
- User manual (M): p.2 pump details (adapter side view), p.27 removal at 120 deg with the cartridge on the spike, p.28 step 7 (cartridge plunger first into the compartment, pump upright) and step 8 (adapter at 90 deg onto the bayonet socket), p.29 adapter side + underside views ("Needle" at the centre of the nose), p.29 step 9 (turn clockwise to the stop, aligned with the housing), p.36 removal; Adapter & Tubing IFU figures (A); owner's product photo; safety notices 2016 (https://laegemiddelstyrelsen.dk/da/udstyr/sikkerhedsmeddelelser/2016/06/~/media/DFF3BCBB31A34F39B619A15AF08DE16D.ashx) and 2022 needle redesign / recall (https://laegemiddelstyrelsen.dk/da/udstyr/sikkerhedsmeddelelser/2022/05/~/media/031629A263BF4404ABB0B58747A4D39B.ashx).
- FDA: no 510(k) for the Insight or its Flex / Tender / Rapid sets (openFDA); Roche entries only for UltraFlex (K122686, K101196) and FlexLink Plus (K143446). No US clearance -> no 510(k) summary with dimensions.

**Interface (how it works):**
1. **The adapter IS the pump's end cap.** The cartridge lies along the 84 mm length and goes in plunger first through the **52 x 19 end face** (M p.28 step 7, "hold the pump upright"). Locked, the adapter covers that whole end face incl. the battery cover ("correctly positioned when it is aligned with the pump's housing", M p.29; D689,523 "end cap removed"; turning back to 90 deg exposes the battery cover, M p.19).
2. **Spike:** "a needle is located at the centre of the adapter nose" (A, M p.29). The nose is a cylindrical cup on the underside near one end; in the design views nothing stands past the rim, so the spike is probably recessed in the cup (ESTIMATE). It must hit the septum centrally and perpendicularly. The cartridge crimp cap stands proud of the compartment floor into that cup; on removal the cartridge stays on the spike (M p.27).
3. **Lock:** bayonet. The nose goes into the notches of the housing with the adapter at 90 deg, then clockwise to the stop (M p.28-29; removal anticlockwise, lift-off at about 120 deg). D689,523 Fig. 6: two arc notches in the bore wall about 180 deg apart (60-80 deg arc each); D720,449 Fig. 5: two lugs on the nose rim on the adapter's long axis, one wide (about 5) and one narrow (about 1.5) = probably keyed.
4. **Tubing:** leaves the far narrow end of the adapter along its long axis, in the underside plane (about 2 above the underside face, centred across the width), through a U notch / hook (D720,449 Figs 1, 2, 5, 6, 8; A). This is the owner's "tubing exits at the bottom".
5. **Seal / vent:** patent: inner O-ring 230 on the cartridge cap (axial support), outer O-ring 235 on the housing face, optional 240 between septum and vent membrane; vent channel 220. Production: "minimum opening pressure adapter vent 0.65 bar" (M App. A); "the adapter is not watertight" (M p.36).
6. **Underside step:** the tubing half of the underside stands 2.5-3.3 further toward the pump than the nose half (D720,449 Fig. 3, A); it probably covers the battery-cover area.

**Dimension table** (multi-source; patents unscaled -> scaled with the pump 84 x 52 x 19 VERIFIED; cross-checks: tubing reads 1.9, cap about 8, adapter L/W 2.67 vs end face 2.74):
| Feature | Value (mm) | Status | Sources / scale |
|---|---|---|---|
| Pump incl. adapter | 84 x 52 x 19 | VERIFIED | M App. A |
| Pump body without adapter | 74-75 | ESTIMATE | 84 - adapter height |
| Adapter length x width | 48-52 x 18-19 (= the end face) | ESTIMATE | D720,449 L/W 2.67 with W 19; M p.29 L/W 2.8; IFU 47.7 |
| Adapter height (base to dome top) | 9-10 | ESTIMATE | D720,449 Figs 3 / 7; IFU 9.0; M ~10 |
| Nose OD / flange at its base | ~13 +-1 / ~15.5 | ESTIMATE | D720,449 Figs 3 / 5 / 7; IFU 13.5 |
| Nose protrusion below the base | 4-7 | ESTIMATE | IFU 4.1; D720,449 5.8-7.3 |
| Nose axis from the nose end | ~12.5 (0.24 L), centred across the width | ESTIMATE | D720,449 Fig. 3 / 5; M p.29 0.29 L |
| Lugs | 2, 180 deg apart on the long axis (locked), ~5 and ~1.5 wide | ESTIMATE | D720,449 Fig. 5 |
| Spike | on the nose axis (VERIFIED), length unknown, recessed in the cup | ESTIMATE | IFU, M p.29 |
| Tubing exit | far end, ~2 above the underside, centred, along the long axis; tubing OD ~1.9 | ESTIMATE | D720,449 Fig. 8 |
| Underside step (tubing half) | 2.5-3.3 | ESTIMATE | D720,449 Fig. 3, IFU |
| Compartment bore / counterbore | ~11.7-12.4 / ~15-17 | ESTIMATE | D689,523 Fig. 6 |
| Bore centre | ~13-14 from the end-face edge, centred in the 19 | ESTIMATE | D689,523 Fig. 6, agrees with the nose |
| Bayonet notches | 2, ~180 deg apart, ~60-80 deg arc, ~1 radial | ESTIMATE | D689,523 Fig. 6 |
| Cartridge cap proud of the compartment floor | 4.5-5.5, cap OD ~8 | ESTIMATE | IFU, M p.28 |
| Cartridge length incl. cap | ~44 | ESTIMATE | M p.2 photo L / OD 4.0 with OD 10.95 |
Conflict to settle by measuring: nose OD (~13) reads larger than the bore (~12); both within +-1 of drawing error. The 2021-22 needle redesign means older drawings may differ from current lots.

**Measure on real parts** (calipers, 3 samples): adapter L / W / H and dome, nose OD / ID / depth, spike free length and tip position vs the nose rim, lug widths / heights / angles (keyed?), underside step depth and extent, tubing exit height / offset / OD, vent location, O-rings; on the cartridge: OD, overall length, cap OD / height, stopper length / position.

**CAD consequence (owner decision 2026-11-24, option A = flush):** variant A takes the Insight end-face cross-section (52 x 19, adapter flush, one outer block for housing + adapter); only the length can beat the Insight. Values in `params.json -> cart.variants.A`.

### 7.7 Variant B: infusion-set candidates, ranked (2026-11-24)
All Luer pump sets have a **female** Luer-lock pump end, and so does the hypodermic needle hub in our B cap: every row needs one **male-male Luer-lock coupler** (e.g. pluriselect Combifix, 25-30 EUR / 10, https://www.pluriselect.com/en/shop/1366; not in the score). DANA uses a **left-hand Luer** ("proprietary LH Luer connection", Dana-i manual p.35, https://myglucosemonitor.com/img/cms/Dana-I_usermanual_English.pdf), so it only slip-fits a standard coupler.
Score = 0.35 price + 0.30 fit + 0.15 priming volume + 0.15 small quantities + 0.05 existing 3D model (each 0-10). V = page / maker document read, E = estimate or snippet.
| # | Set | Maker | EUR / set to DE | Pack | Pump end | Site part | Tubing / priming | Score | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | **B. Braun Venofix A 25G 0.5 x 19, PZN 17935284** https://www.docmorris.de/venofix-a-venenpunktionsb25-g-05x19mm/17935284 | B. Braun, EU | 0.59 (V), ~0.85 with shipping at 20 (E) | 1 | lock fitting with closure cone (V), female Luer-lock ISO 80369-7 (E) | steel winged needle | 30 cm (V), ~0.2-0.4 ml (E) | **8.85** | V/E |
| 2 | Butterfly 23G, PZN 08482613 https://www.docmorris.de/butterfly-infusionszubehoer-23-g-blau/08482613 | 1001 Artikel Medical, EU | 1.42 (V) | 1 | Luer-lock (V), female (E) | steel butterfly | n/v | 8.15 | V/E |
| 3 | Neria Guard 12 cm https://cicaclic-prod.dxp.convatec.com/siteassets/infusion-care/infusion-care-learning-media/product-range-brochure.pdf | Convatec / Unomedical, EU | ~10-13 (E, no DE shop found) | 10 | standard Luer-lock (V) | soft cannula 6 / 9 mm | **12 cm / ~0.04 ml (V)** | 7.05 | V/E |
| 4 | mylife Orbit micro Luer, PZN 09892448 https://www.medpex.de/mylife-orbitmicro-5-5-mm-60-cm-infusionsset/09892448 | Ypsomed, CH | ~12 (E) | 10 | standard Luer-lock (V) | 31G steel 5.5 mm | 60 cm / ~0.1 ml (E) | 7.05 | V/E |
| 5 | AliExpress veterinary butterfly set 1005009176774218 - **FOR BENCH (WATER) TESTS ONLY - sterility / quality / approval unknown, never for use on a person** | unknown, CN | 0.14 (13.89 / 100, free delivery) | 100 | Luer (slip / lock unknown) | steel butterfly | unknown | 6.75 | V price / E |
| 6 | BD Saf-T-Intima 24G Y port, PZN 17304448 | BD, EU | 17.69 (snippet) | 1 | female Luer port (E) | soft catheter | short (E) | 6.65 | E |
| 7 | Accu-Chek FlexLink | Roche | ~13.7 (E) | 10 | Luer-lock female (E) | soft 6 / 8 / 10 mm | 30-110 cm | 6.05 | E |
| 8 | DANA Easy-Release https://www.tk-pharma.de/insulinpumpentherapie/katheter-und-transfersets/776/dana-easy-release | SOOIL, KR | 7.25 + shipping (V), out of stock | 10 | **left-hand Luer** (V) | 29G steel 4.5 / 7 / 9 | 60 cm / ~0.13 ml (E) | 4.95 | V/E |
| 9 | Insight Adapter & Tubing 70 cm (variant A, not B) | Roche | 4.84 (48.44 / 10, medizinfuchs) | 10 | proprietary Insight | separate Insight Flex | 70 cm | 4.7 | V snippet |
| 10 | KORU HIgH-Flo SCIG | KORU, US | n/v | 10-20 | "custom Luer" (E) | 24-26G steel | 0.2-1.4 ml (E) | 4.45 | E |
| 11 | MiniMed Quick-set | Medtronic | ~12.5-15 (E) | 10 | MiniMed connector in DE (E) | soft 6 / 9 | 46-110 cm | 4.25 | E |
| 12 | AliExpress "21G needle Luer-lock infusion set" (listing title translated) 1005012875217825 - **FOR BENCH (WATER) TESTS ONLY - sterility / quality / approval unknown, never for use on a person** | unknown, CN | 17.22, free shipping | ? | Luer-lock (E) | 21G steel | unknown | 4.25 | V price / E |
| 13 | Alibaba "Disposable Insulin Pump Infusion Cannula Set" 1602018325951 - **FOR BENCH (WATER) TESTS ONLY - sterility / quality / approval unknown, never for use on a person** | UNVERIFIED | UNVERIFIED | MOQ UNVERIFIED | UNVERIFIED | UNVERIFIED | UNVERIFIED | 1.65 | page did not open (captcha, not bypassed), no snippet found; CE / ISO claims UNVERIFIED |
Searched without usable results: Medtrum nano / A6 and MicroTech Equil are patch pumps (no tubing set, E); no Weigao / Apex / Fornia / KR / JP / IN pump-set listings; DHgate, Amazon.de nothing relevant; Made-in-China only IV sets with large MOQs; eBay.de pump sets 55-190 EUR per box (resellers, some expired).
**Pick for the water bench: #1 Venofix A 25G** (0.59 EUR, single pieces, EU-made, locking Luer) + one male-male Luer-lock coupler; outlet into a container / onto a scale. If dead volume or realistic pump-set flow matters (occlusion timing), use **#3 Neria Guard 12 cm** (0.04 ml, standard Luer-lock; source via pharmacy / Convatec DE).

### 7.9 The real adapter (owner photos, 2026-11-25; supersedes the lug / groove / key-step reading of 7.6)
Three photos of the owner's Insight Adapter & Tubing (underside straight on, two side profiles; not committed), scaled with the adapter width = 19.0 (~21 px/mm): all values **PHOTO-ESTIMATE +-0.5-1 mm**.
- Underside flat; a dark **cup** (female socket: OD ~10.3, ID ~8.4, 4 internal ribs, needle hole in the centre) ~4.7 proud, centre ~10.3 from the near end; an **outward lip** on the cup rim (~11.1 x 0.6) = the bayonet lugs, interrupted by flats on the long axis (lips across the width, ~80 deg each: VERIFY).
- A **white seal ring** (OD ~13.5, ~0.8 thick) around the cup base on the flat face.
- The far half of the underside stands ~2.5 proud beyond an **arc** ~24 from the cup axis; at that arc a **hook / spring tongue** ~7 off the long axis (latch at the flush position).
- Tubing leaves the far end in an underside channel; 2 small screws at the cup end, further holes along the body, a white dot mid-length (vent or magnet).
- Outer side domed, thickest (~9-10) mid-length; length ~49-50 (L/W 2.6).
- Mounting (owner): put on at 90 deg (sticking out), turned 90 deg down until flush, the hook latches.
So the pump side is a socket with 2 inward retaining tabs and 2 entry gaps (not a groove for lugs on the adapter), a flat seal face, a recess concentric with the socket for the raised far half, and a catch for the hook. Implemented in `params.json -> cart.variants.A.adapter.cup` / `receiver` (type `cup_bayonet`), coupons `mechanical/out/v010-cart/coupons/A_lock/` (README with the 10 measurements to take). Earlier 7.6 values for the nose (13), lugs, key step and pocket are wrong for this part.

### 7.8 Variant B: realistic soft-cannula Luer sets (owner correction 2026-11-24: soft Teflon cannula + adhesive + inserter, standard Luer-lock pump end, cheap; bench into a container / foam / gel, water only)
Score = 0.35 price per set delivered to DE at 50-100 + 0.25 soft cannula / adhesive / inserter + 0.20 Luer-lock pump end + 0.10 small tubing volume + 0.10 MOQ / sample. V = read on the page, E = estimate, U = UNVERIFIED (snippet only).
| # | Set / supplier | Cannula | Inserter / adhesive | Pump end | Tubing | Price per set | MOQ | Score |
|---|---|---|---|---|---|---|---|---|
| 1 | **Zhengzhou Phray "Luer lock insulin pump infusion set"** (pump maker, PH300 / 310 / 820): page https://phray.ecer.com/sale-8277037-insulin-pump-reservoirs-advanced-lock-insulin-pump-infusion-sets-luer-lock-insulin-pump-infusion-set.html now **HTTP 410**; contact via https://phray.en.alibaba.com/ (captcha for scripts, not bypassed). **BENCH (WATER) ONLY - sterility / quality / approval unknown, never for use on a person** | Teflon 26G, 6 / 9 mm, 90 deg (U) | "Fast Settle-I" inserter, adhesive (U) | "Luer lock", "fits Dana / Luer-lock pumps" (U): **thread direction must be confirmed** (DANA = left-hand) | 70 / 90 / 110 cm (U), ~0.1-0.15 ml (E) | US$2.5 (U) -> ~EUR 4.2 delivered at 50, ~3.7 at 100 (express + 19 % VAT + courier fee, E) | 50 (U) | 8.15 |
| 2 | Unomedical Inset 30, 13 mm, 43", Luer (Medex Supply, US) https://medexsupply.com/unomedical-inset-30-infusion-set-13mm-cannula-43-tubing-10-box | Teflon 13 mm, 30 deg (V) | integrated inserter, adhesive (E) | Luer lock (U) | 110 cm, ~0.2 ml (E) | US$11.50 (U), ~EUR 16 delivered (E) | 10 | 6.95 |
| 3 | Neria Guard 12 cm (Convatec, EU) | soft 6 / 9 mm 90 deg (V) | manual guarded insertion (E) | standard Luer (V) | 12 cm, 0.04 ml (V) | ~EUR 10-13 (E), no DE shop found | 10 | 6.75 |
| 4 | mylife Orbit soft 6 mm / 60 cm, PZN 18031001 https://www.medizinfuchs.de/mylife-orbit-soft.html | soft 6 / 9 mm 90 deg (E) | manual, adhesive (E) | standard Luer (V maker; Luer version of this PZN E) | 60 cm ~0.1 ml (E) | EUR 16.40 (V) | 10 | 6.40 |
| 5 | Accu-Chek FlexLink 10 / 60, PZN 01022512 https://www.medikamente-per-klick.de/accu-chek-flexlink-10-60-mit-adapter-infusionsset-10st-01022512 | Teflon 6 / 8 / 10 mm 90 deg (V) | LinkAssist inserter separate (E) | Luer (V) | 30-110 cm | EUR 13.69 (V), sold out | 10 | 6.35 |
| 6 | MiniMed Quick-set Luer 9 mm / 23" (Vitality Medical, US) | soft 90 deg (V) | Quick-serter separate | Luer lock (V) | 58 cm | US$15.31 (V), ~EUR 18 delivered (E) | 10 | 6.10 |
| 7 | Nanjing Longcare "Quick-Set detachable" https://longcaremed.en.made-in-china.com/product/cGIYywgKESRl/China-Factory-Supply-of-Quick-Set-Detachable-Infusion-Device.html **BENCH (WATER) ONLY - sterility / quality / approval unknown, never for use on a person** | PTFE 90 deg or steel (V) | adhesive (E) | **Paradigm / "SC1", not Luer (V)** | 60-110 cm (V) | US$4.00 (V) | 1000 (V) | 5.55 |
| 8 | DANA Inset II 6 mm / 60 cm, PZN 20014406 | soft 90 deg | integrated inserter | **left-hand Luer: does not lock** | 46-80 cm | EUR 18.40 (V) | 10 | 5.40 |
| 9 | Ypsomed Soft-Release-O S6061 (DANA), PZN 17877598 | soft | n/s | DANA left-hand (E) | 60 / 80 cm | EUR 15.50 (V) | 10 | 5.00 |
| 10 | Chinese NMPA class III set (maker n/a, distributor https://www.jmmedical.cn/product/i806240.html) **BENCH (WATER) ONLY - sterility / quality / approval unknown, never for use on a person** | FEP soft (V) | inserter + adhesive (V) | female conical, thread direction n/a | n/a | n/a | n/a | 4.6 |
Ruled out: Nanchang Yili and Changzhou Sunton (gravity IV sets with burette / 150-200 cm PVC, MOQ 50,000-100,000, "insulin pump" only in the title, V); iLet Inset I Luer (placeholder price only); AliExpress (8 searches, no pump sets); Alibaba / GlobalSources / DHgate / 1688 / Taobao not readable by scripts (captcha / 429, not bypassed).
**Pick: #1 Phray (UNVERIFIED, page gone) -> request samples first** via the Alibaba storefront: state "engineering bench test, water only"; ask for 5-10 paid samples by express before MOQ 50; ask in writing: right-hand ISO 80369-7 female Luer lock or DANA left-hand (photo screwed onto a standard male Luer), cannula material / gauge / length / angle, inserter single-use and included, tubing length / ID / priming volume, CE / ISO 13485 certificates, DAP Germany quote at 50 and 100, HS code (9018.39, E). The owner places and pays the order.
**EU fallback (buyable now):** Accu-Chek FlexLink (PZN 01022512, ~EUR 13.7, standard Luer, Teflon 90 deg; often out of stock) -> else mylife Orbit soft (PZN 18031001, EUR 16.40); Unomedical Inset 30 (#2) if a built-in inserter matters; Neria Guard 12 cm (#3) if dead volume matters. Avoid DANA sets (left-hand Luer). All via the male-male Luer-lock coupler (K6).
