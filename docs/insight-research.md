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
| Piston rod | "piston rod" (EN) / "Gewindestange" = threaded rod (DE); rewinds automatically at each cartridge change | VERIFIED | M p.27, H |
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
| CAD placeholder (Penfill-class glass) | OD 11.6, ID 9.7, barrel 36, neck 7.2 x 4.5, cap 7.8 x 3.0, stopper 9.7 x 6.0 | ESTIMATE | `params.json -> cart.cartridge` |

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
