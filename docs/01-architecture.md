# System architecture

```mermaid
flowchart LR
  subgraph Phone["iPhone – Trio"]
    T[Trio algorithm] --> PK1[OpenPatchKit<br/>dedicated PumpManager]
    T --> PK2[OmnipodKit<br/>DASH, unmodified]
  end
  PK1 -- "BLE: OpenPatch protocol" --> FW
  PK2 -- "BLE: DASH protocol (pod emulation)" --> FW
  subgraph Pod["OpenPatch Pod (reusable)"]
    FW[ISP1807 module (nRF52840) firmware<br/>delivery engine + safety supervisor] --> DRV[STSPIN220]
    WD[TPL5010 watchdog] --> SW[Load switch]
    FW --> SW --> DRV --> M[Ø6 mm stepper + 10:1] --> S[Spindle M1.6] --> K[Stadium piston]
    ENC[Hall encoder] --> FW
    QI[Qi coil + BQ51003] --> CH[BQ25120A] --> B[LiPo ~35–45 mAh]
    K --> R[(Reservoir 0.7 / 1 / 2 ml)] --> N[30G needle]
    SEP[Fill septum] --> R
  end
  N --> C[Accu-Chek Insight Flex<br/>cannula head] --> Skin
```

## Decisions

| Topic | Decision | Why |
|---|---|---|
| "Own chip" | **No ASIC.** Rev A: custom 4-layer board around the ISP1807 SiP module (nRF52840, antenna integrated). Rev B: bare nRF54L15 | An ASIC costs six to seven figures and takes 1–2 years. PCB fabs (JLCPCB/PCBWay) do not manufacture ICs. We reach the goal of "super optimized" through layout, firmware and low-power modes. |
| Drive | Stepper motor + spindle + piston | Accurate, verifiable with an encoder, principle not patented. Piezo pumps are not validated with insulin. |
| Flatness | **Stadium reservoir 16 × 5 mm** instead of a round cylinder | A round 2 ml cylinder would need Ø ≥ 9.5 mm and therefore ≥ 12 mm build height. With the stadium cross-section, ≤ 8.5 mm is possible. |
| Sizes | Only the length varies (stroke 9.4 / 13.4 / 26.8 mm) | Same electronics, same drive, same cannula pocket |
| Charging | Qi (BQ51003), charging only when detached | No connector hole, so it is sealed; no heat at the insulin during delivery |
| Trio | (1) dedicated `OpenPatchKit`, (2) DASH emulation | (1) shows real values and stays clean. (2) works immediately with an unmodified Trio. The reference implementation is nightscout/ESP-Sim. |
| Omnipod 5 | **not emulated** | O5 pairing uses signed P-256 transcripts and an external key manager with App Attest. Compared with DASH, this offers no advantage. |
| License | Hardware CERN-OHL-S v2, iOS kit MIT, firmware GPL-3.0 (because of ESP-Sim in DASH mode) | Genuine open source |

## What Trio does in its source code (verified)

- `nightscout/Trio/.gitmodules`: pumps are submodules (OmnipodKit, DanaKit, MedtrumKit, MinimedKit, AccuChekKit …).
- `Trio/Sources/APS/Devices/DeviceCatalog.swift` → `DeviceCatalog.pumps`: a new pump needs an entry there.
- `loopandlearn/OmnipodKit/OmnipodKit/Bluetooth/`: DASH service `1A7E4024-E3ED-4464-8B7E-751E03D0DC5F`, command `…2441`, data `…2442`. Pairing via X25519 + AES-CMAC to the LTK, session via EAP-AKA/Milenage, messages via AES-128-CCM. Details are in `firmware/docs/dash-compat.md`.
