# Patents & prior art

Research as of: 2026-11-18. **Not legal advice.** The expiry dates come from Google Patents, and Google itself labels them as estimates. Term extensions (PTA/SPC) can make a patent expire later than "filing + 20 years". For purely private, non-commercial personal use, Germany additionally has the exemption in § 11 No. 1 PatG. You should check that yourself too.

## What we adopt from this (expired → free to use)

| Patent | Owner | Status | Idea we use |
|---|---|---|---|
| [US6740059B2](https://patents.google.com/patent/US6740059B2/en) | Insulet | expired 2021 | Reservoir 2–3 ml, filling with a syringe through a self-sealing silicone septum |
| [US6656159B2](https://patents.google.com/patent/US6656159B2/en) | Insulet | expired 2022 | Spindle drive with backstop; fixed pulse size 0.5 µl (= 0.05 U) |
| [US7250037B2](https://patents.google.com/patent/US7250037B2/en) | BD | expired 2025 | flat reservoir: rigid, domed shell with film (alternative to our stadium reservoir) |
| [US4781688](https://patents.google.com/patent/US4781688) | – | expired | compressible, flexible reservoir |

## Probably still in force → design around or choose an alternative

| Patent | Owner | Core | Our differentiation |
|---|---|---|---|
| [US7935104B2](https://patents.google.com/patent/US7935104B2/en) (until approx. 2029) | Medingo → Roche (Accu-Chek Solo) | Reusable part with motor and electronics, disposable part with battery, bag and peristaltic drive | With us, **everything** is in the reusable pod, including the battery and rigid piston reservoir. Only the purchased cannula is disposable. No peristaltic drive. |
| [US7771392](https://patents.google.com/patent/US7771392) | Roche/Disetronic | One SMA wire drives two ratchet wheels | We use a stepper motor instead of SMA |
| [US8535269B2](https://patents.google.com/patent/US8535269B2/en) (until approx. 2029) | Roche | Insertion head with needle guard in the handle (presumably Insight Flex family) | We **buy** the cannula and only plug onto it. We do not replicate the head. |
| Tandem [US12661446B2](https://mtec-sc.org/patents/US-12661446-B2) | Tandem | Cartridge is inserted at an angle and locked by turning, encoder on the spindle | Encoder alone is prior art; we do not adopt the locking geometry |
| EOFlow, CeQur, SteadyMed (elliptical reservoir [US10112005](https://patents.justia.com/patent/10112005)) | various | Electroosmosis, pressure source with restrictor, **non-round reservoirs** | ⚠️ Our stadium reservoir is close to SteadyMed (elliptical) and US11980739 (non-round piston). Read the claims carefully before publication or sale. Fallback: BD film reservoir (expired). |

## Occlusion detection

Medtronic holds several patents on this, e.g. [US7892206](https://patents.justia.com/patent/7892206) (mean motor current) and [US8864739](https://patents.google.com/patent/US8864739) (force × current). Older variants such as [US2001/0034502](https://patents.justia.com/patent/20010034502) from 2001 have expired. We use **encoder slip** (steps without measured spindle rotation) and a simple current threshold. Both are old prior art.

## Accu-Chek Insight Flex – interface

- According to the [IFU](https://www.accu-chek.co.uk/document/accu-chek-insight-flex-instructions-use/download), the set consists of a head ("cannula") and tubing. The tubing is plugged onto the connector plate and released again by squeezing the side wings. It is **not a Luer connector**. After each docking, 0.7 U is filled ("cannula priming").
- Dimensions, CAD models and teardowns are **not public**. You have to measure the geometry yourself, see `mechanical/cannula-measurement.md`.
- Consequence for the firmware: offer 0.7 U cannula priming on **every re-attachment** of the pod. Anyone who removes the pod often loses insulin this way.

## Further references

- Teardown of the Omnipod drive: [Hackaday 2023](https://hackaday.com/2023/04/25/insulin-pump-teardown-shows-one-motor-does-many-jobs), [Lumafield](https://lumafield.com/de/scan-of-the-month/health-wearables)
- Open-source pump (syringe pump, HardwareX 2022): [UCBioengineering/open_source_insulin_pump](https://github.com/UCBioengineering/open_source_insulin_pump)
- Piezo micropumps (Bartels mp6): There is no validation for insulin. Fraunhofer EMFT reports dosing errors with insulin due to bubble formation ([link](https://emft.fraunhofer.de/en/projects-fraunhofer-emft/study-optimized-insulin-dosing-micropumps.html)). → That is why we use a piston drive.
- Medtrum TouchCare Nano (reusable base, 200 U): 40.5 × 31.5 × 11.5 mm, 13.8 g. This is our realistic size benchmark.
