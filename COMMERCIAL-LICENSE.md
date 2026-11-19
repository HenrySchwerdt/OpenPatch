# OpenPatch Commercial "Fair-Price" Licence

> **DRAFT TERM SHEET AND LICENCE TEMPLATE. NOT AN OFFER. NOT LEGAL ADVICE.**
> To be reviewed by a lawyer for licensing law and EU/German competition law before any use. All figures and clauses are proposals. OpenPatch is a test project and **not a medical device**; see [`DISCLAIMER.md`](DISCLAIMER.md).

Licensor: the OpenPatch maintainer (owner of the GitHub repository `HenrySchwerdt/ai-insulin-pump`) ("Licensor").
Licensee: the party signing a licence agreement based on this template.

## 0. Why this structure (intent, non-binding)

The terms are designed so that open development is the commercially rational choice for companies:
- **Be first, lose nothing:** the first company that funds approval and clinical trials (the sponsor) gets its audited investment back from every later licensee that benefits (§3a). Being first is therefore not a subsidy for competitors but a recoverable investment, and the sponsor sets the reference product.
- **Followers pay fairly, patients pay little:** followers repay out of their own capped margin (§2), never via a higher end-customer price.
- **Shared evidence grows:** the 5 % levy (§3) funds studies and verification whose results are open to everyone, so every licensee benefits from a growing common body of evidence.
- **Improvements flow back:** share-back (§7) and post-market fault reporting into the shared fault catalogue (§4) keep improving one common, safer design instead of fragmenting it into closed forks.

## 1. Scope

The community licences ([`LICENSE.md`](LICENSE.md)) cover non-commercial use only. This licence is **required for any commercial manufacture, sale, rental, lease, or paid or advertising-funded service** based on OpenPatch hardware, firmware, specifications or documentation ("Licensed Material"), except `ios/` (GPL-3.0-or-later, free for all users under its own terms).

Grant: non-exclusive, non-transferable, worldwide, revocable only per section 11, to make, have made, sell and service products using the Licensed Material, including contributions covered by [`CLA.md`](CLA.md).

## 1a. Excluded: dock insert / cannula adapter

The **dock insert (cannula adapter)** and the **pod-side dock interface specification** are deliberately excluded from this licence and from all of its obligations (price cap, levy, recoupment, share-back). They are licensed permissively under **CERN-OHL-P-2.0** (see [`LICENSE.md`](LICENSE.md)). Reason: the cannula is a third-party consumable, every manufacturer will adapt the insert to the infusion set it supports, and **each manufacturer must obtain regulatory approval for its own adapter / infusion-set combination anyway**. Recoupment under section 3a therefore never covers adapter or infusion-set approval work. The safety obligations of section 4 still apply to the pump: an insert must meet the frozen dock interface (needle alignment, dock-magnet position for the DOCKED interlock) and pass the dock-related conformance tests.

## 2. Price cap (maximum price)

2.1 The end-customer price of a Product (net of taxes) must not exceed **fully-loaded unit cost + 30 %**.

2.2 **Fully-loaded unit cost** comprises: bill of materials; assembly; test; quality assurance; amortisation of regulatory, QA and certification costs over planned volume; distribution and logistics; warranty reserve. It excludes profit, and excludes unrelated overhead not attributable to the Product.

2.3 The Licensee must (a) provide an **annual cost statement audited** by an independent auditor, and (b) **publish a cost breakdown per Product** (by the categories in 2.2) on its website.

2.4 This is a **maximum** price only. The Licensee remains free to sell lower; the Licensor never sets a minimum or fixed price. Resellers are not bound by any price term in the Licensor's name.

> *Legal review flag:* maximum resale prices are generally treated more leniently than fixed or minimum prices under EU vertical rules (Reg. (EU) 2022/720, Art. 4(a)), but a cap imposed on a manufacturer-licensee (not only a reseller), market-share effects, German GWB and the interplay with healthcare pricing rules need review.

## 3. Clinical-trial levy

3.1 The Licensee pays **5 % of net revenue** from Products to an **open, independently administered fund** for clinical studies, verification and validation, and regulatory documentation.

3.2 Results funded must be **published openly** for all licensees and the community.

3.3 Fund governance (independent administrator, allocation criteria, reporting, conflict-of-interest rules) is a placeholder: *[to be defined; legal vehicle e.g. foundation or trust, to be reviewed]*. Until the fund exists, levies are held in escrow.

## 3a. Clinical & regulatory investment recoupment

> DRAFT, not legal advice. Needs review for EU/German competition law (technology transfer rules, the Technology Transfer Block Exemption Regulation (TTBER, current version to be checked), Art. 101 TFEU, GWB) and for EU MDR.

3a.1 **Sponsor.** A licensee that funds regulatory approval and/or clinical trials for an OpenPatch-based product (the "Sponsor") may register its investment with the independent administrator (the same body as the fund in section 3).

3a.2 **Recoupment payment.** Every **other** commercial licensee that distributes an OpenPatch-based product relying on, or benefiting from, the Sponsor's approval work or clinical evidence (a "Payer") pays a fixed share of its margin, **draft value 30 % of its gross margin per unit** *(placeholder, adjustable)*, to the Sponsor via the administrator, until the Sponsor's **verified, audited investment is recovered**. Gross margin per unit = end-customer price (net of taxes) minus fully-loaded unit cost (section 2.2), as shown in the Payer's audited cost statement.

3a.3 **Pro-rata.** Recoupment is shared among all paying Payers pro rata to their payments; the Sponsor's own sales do not repay it. The Sponsor receives no more than its verified investment plus the capped return (3a.4).

3a.4 **Capped first-mover return.** On top of the verified investment the Sponsor may recover a **capped return of 20 % of the recoverable investment** *(draft value, decision 2026-11-19)*, to reward being first to approve. No interest beyond this cap; the total recoverable amount is investment × 1.20.

3a.5 **Automatic end.** The obligation ends automatically once the verified investment (plus any agreed capped return) is covered. The administrator tracks repayment and publishes the status.

3a.6 **Verification.** The administrator verifies the Sponsor's cost statement (independent audit; only eligible, documented, external and directly attributable costs) and tracks all payments.

3a.7 **Sponsor's counter-obligations.** The Sponsor makes the clinical data, technical documentation and test reports available to paying Payers (under EU MDR, another manufacturer can generally rely on clinical data or claim equivalence only with sufficient access to the data and documentation; *flag for legal/regulatory review*), and publishes the results openly once recovered, or after at most *[5]* years, whichever is earlier.

3a.8 **Interaction with the price cap (section 2).** Recoupment payments are paid **out of the Payer's capped margin** and are **not** added to the cost basis or the price. The cap stays "unit cost + 30 %" regardless of recoupment. Rationale: this variant keeps end-customer prices lowest; adding recoupment to the cost basis would let the cap, and thus prices, rise. Consequence: a 30 % recoupment share leaves the Payer with 70 % of its permitted margin until the Sponsor is repaid. *(The Sponsor's own amortised costs remain in its cost basis under 2.2; amounts already recovered through recoupment or the levy must not be amortised again.)*

3a.9 **Interaction with the levy (section 3).** The 5 % clinical-trial fund may co-finance Sponsor trials. **Amounts funded by the levy are excluded from the Sponsor's recoverable investment** (no double recovery).

3a.10 **Worked example (illustrative numbers only).**
- Sponsor invests EUR 2,000,000 in approval and trials; EUR 500,000 of it is funded by the levy fund, so the recoverable investment is **EUR 1,500,000**, plus the capped 20 % return = **EUR 1,800,000** total recoverable.
- Payer A and Payer B each sell products at unit cost EUR 100, price cap EUR 130 (cost + 30 %), i.e. gross margin EUR 30 per unit. Recoupment = 30 % of EUR 30 = **EUR 9 per unit**; Payer keeps EUR 21; the price stays EUR 130.
- Payer A sells 100,000 units (EUR 900,000), Payer B sells 80,000 units (EUR 720,000). Together EUR 1,620,000, which is below the EUR 1,800,000 owed, so both keep paying EUR 9 per unit on further sales until a further EUR 180,000 is collected (e.g. 20,000 more units in total). Then the obligation ends automatically, pro rata to payments due; any excess is not collected or is refunded. From then on the clinical data and reports are published openly and Payers keep the full EUR 30 margin.
- The 5 % levy is separate: it is 5 % of net revenue (EUR 6.50 per unit at price EUR 130) and goes to the fund, not the Sponsor.

## 4. Safety obligations

The Licensee shall, in every Product and release:

1. keep the **hardware interlock** unweakened: motor only with MCU enable **and** watchdog **and** dock/reverse gating, hardware step budget, over-current cut (spec §7, §7a; [`docs/02-safety.md`](docs/02-safety.md));
2. keep the **diagnostic code system** and **component-level fault reporting** unweakened ([`docs/06-diagnostics.md`](docs/06-diagnostics.md));
3. not relax safety limits (spec §7) compared with the Licensed Material;
4. **pass the project's conformance suite** for every release: simulation scenarios, firmware tests and bench procedures, and keep the results on record;
5. perform **post-market fault reporting** into the shared fault catalogue;
6. **publish all changes to safety-relevant parts** (see section 7);
7. obtain **all regulatory approvals itself** (EU MDR, FDA or equivalent) and bear the manufacturer's responsibilities. The Licensor grants no approval, makes no medical claim and gives **no warranty**; the Licensee must not state or imply that the Licensor approved or endorses a Product.

## 5. Fees

No fee other than the levy in section 3. *[Placeholder: administrative fee, if any.]*

## 6. Trademark

"OpenPatch" is not a registered trademark. *[Placeholder: naming rules for compatible products.]*

## 7. Share-back

Improvements and modifications to the Licensed Material made by the Licensee (hardware, firmware, documentation, test procedures) must be published under the **community licence** (CC BY-NC-SA 4.0 / PolyForm Noncommercial 1.0.0) within *[90]* days of first shipment, and safety-relevant changes before first shipment. The Licensor may include them in the project, also under this commercial licence.

## 8. Audit

The Licensor or an independent auditor it appoints may, on *[30]* days' notice and at most once a year (more often on reasonable suspicion), audit records needed to verify sections 2 to 4 (cost statements, revenue, conformance results, fault reports), under confidentiality.

## 9. Warranty and liability

The Licensed Material is provided "as is". The Licensor excludes warranty and, to the extent legally permitted, liability. The Licensee indemnifies the Licensor against third-party claims arising from the Licensee's Products. *[Mandatory German-law limits on liability exclusion to be reviewed.]*

## 10. Term

*[Placeholder: term of e.g. 5 years, renewable.]*

## 11. Termination

The Licensor may terminate for material breach (including exceeding the price cap, non-payment of the levy, weakening the safety obligations, failing an audit) if not cured within *[30]* days; immediately for safety breaches that endanger persons. On termination, the Licensee stops new manufacture and sale and handles post-market obligations for units in the field.

## 12. Governing law and venue

*[Placeholder: law of the Federal Republic of Germany; venue to be defined; exclusion of the UN Sales Convention.]*

## Open questions for legal review

- Price cap vs. EU/German competition law (Art. 101 TFEU, Reg. 2022/720, GWB), and enforceability against downstream resellers.
- Whether a licence with an audited price cap and levy is compatible with CC BY-NC-SA 4.0 and PolyForm Noncommercial (dual licensing of contributions needs the CLA).
- Recoupment (3a): TTBER/Art. 101 TFEU/GWB review; MDR access to clinical data and equivalence; verification standards; payer fairness.
- Legal form and governance of the clinical-trial fund; tax treatment of the levy.
- Consistency with MDR manufacturer duties; liability allocation and product-liability law.
- Whether a "non-commercial" restriction is clear enough for self-builders and research (CC BY-NC grey areas).
