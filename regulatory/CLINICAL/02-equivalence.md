# 02 Equivalence analysis: generally NOT available for a new open device

> Test project. This explains why a clinical-equivalence route is unlikely, so that nobody plans on it.

## 1. What MDR requires (Art. 61(4), 61(5), MDCG 2020-5)

Equivalence to another device requires demonstrated **technical, biological and clinical** equivalence, assessed on a detailed comparison of characteristics (design, specifications, materials, principles of operation, software, conditions of use, critical performance). For implantable and class III devices the manufacturers must additionally have a **contract granting full access to the equivalent device's technical documentation** (Art. 61(5)). For other classes the manufacturer must still demonstrate sufficient levels of access to the data of the equivalent device. **[VERIFY exact text for class IIb]**

## 2. Why it does not apply here

| Reason | Detail |
|---|---|
| New design | a reusable detachable pod with a CNC reservoir, geared stepper with leadscrew, automatic draw refill and a two-pod handover does not match an existing marketed pump in design, materials, software or critical performance |
| No access to others' documentation | competing manufacturers' technical files and clinical data are confidential; no contracts exist |
| Software and algorithm separation | the pump is paired with third-party controllers whose behaviour is part of the clinical use |
| Third-party cannula combination | not validated by the maker |
| Open licensing does not create data access | the commercial licence offers **sponsor-to-licensee** sharing of the sponsor's evidence (`../../COMMERCIAL-LICENSE.md` section 3a.7); that is access to the *first OpenPatch sponsor's* data, which exists only after a sponsor generates it |
| Equivalence across OpenPatch manufacturers | a later licensee's device may claim equivalence to the sponsor's OpenPatch device **only if** it is technically identical and the sponsor grants access (the MDR access requirement); changes in housing, adapter, battery, software or manufacturing process must be assessed |

## 3. What follows

Plan for **own clinical evidence**: clinical investigation(s) and/or a justified use of existing clinical data for well-established technologies, plus literature on the state of the art. The justification for any reduced clinical investigation (Art. 61(10), only where non-clinical testing suffices) must be strong and is **unlikely for an insulin pump**. See `03-investigation-evidence-list.md`.

## 4. The FDA analogue

510(k) substantial equivalence with an existing ACE pump predicate concerns **intended use and technological characteristics**, with performance data (bench, human factors, software, cybersecurity, interoperability). It does not need access to the predicate manufacturer's files. This is an important difference between EU and US routes (`../ROADMAP.md`).
