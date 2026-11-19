// Licence and fair-price model page: plain-language explanation, money-flow diagram and a payback calculator.
import { blobUrl } from './lib.mjs';

const L = (p, t) => `<a href="${blobUrl(p)}">${t ?? p}</a>`;

function flowSvg() {
  return `<svg class="flow" viewBox="0 0 640 330" role="img" aria-labelledby="ft fd">
<title id="ft">Money flow of the Fair-Price licence</title>
<desc id="fd">Customers pay the manufacturer a price of at most unit cost plus 30 percent. The manufacturer pays 5 percent of net revenue into an open clinical-trial fund and, while the sponsor's investment is not yet repaid, 30 percent of its margin per unit to the sponsor through an independent administrator. The sponsor funded approval and trials. When repaid, the clinical data become public.</desc>
<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" class="head"/></marker></defs>
<rect class="n" x="10" y="130" width="120" height="64" rx="3"/><text x="70" y="158" text-anchor="middle">Patients and</text><text x="70" y="176" text-anchor="middle">care providers</text>
<path class="a" d="M130 162H236" marker-end="url(#ar)"/><text class="t" x="183" y="150" text-anchor="middle">price</text><text class="t" x="183" y="184" text-anchor="middle">≤ cost + 30 %</text>
<rect class="n strong" x="240" y="120" width="150" height="84" rx="3"/><text x="315" y="148" text-anchor="middle">Follower</text><text x="315" y="166" text-anchor="middle">manufacturer</text><text class="t" x="315" y="188" text-anchor="middle">licensee, own approval</text>
<path class="a" d="M315 120V66H430" marker-end="url(#ar)"/><text class="t" x="322" y="96">5 % of net revenue</text>
<rect class="n" x="434" y="36" width="196" height="60" rx="3"/><text x="532" y="62" text-anchor="middle">Open clinical-trial fund</text><text class="t" x="532" y="80" text-anchor="middle">results published</text>
<path class="a" d="M315 204V270H430" marker-end="url(#ar)"/><text class="t" x="322" y="236">30 % of margin per unit</text><text class="t" x="322" y="252">until repaid, from the margin</text>
<rect class="n" x="434" y="240" width="196" height="64" rx="3"/><text x="532" y="266" text-anchor="middle">Sponsor (first mover)</text><text class="t" x="532" y="284" text-anchor="middle">audited investment + max 20 %</text>
<path class="a dash" d="M532 96V240" marker-end="url(#ar)"/><text class="t" x="540" y="172">fund may co-finance</text><text class="t" x="540" y="188">trials, excluded from</text><text class="t" x="540" y="204">sponsor recovery</text>
</svg>`;
}

export function licence({ root }) {
  return `
<header class="pagehead">
  <p class="kicker">Licence and fair-price model</p>
  <h1>How OpenPatch is licensed, and why</h1>
  <p class="lede">Free for study, research and self-building. Fair-priced for anyone who wants to sell it. This page explains the whole model in plain language, including the money flow. The legal texts on GitHub are authoritative.</p>
</header>

<div class="danger" role="note" aria-labelledby="dr-h">
  <h2 id="dr-h">Draft. Not legal advice. Under legal review.</h2>
  <ul>
    <li>The commercial "Fair-Price" licence is a <strong>draft term sheet, not an offer</strong>. Every figure and clause is a proposal and is being reviewed by a lawyer (EU and German competition law, medical device rules). Nothing here binds anyone yet.</li>
    <li>This is <strong>source-available, not OSI open source</strong>: non-commercial restrictions do not meet the Open Source Definition. Do not call the project "open source" in the strict sense.</li>
    <li><strong>Test project, not a medical device. Never wear it.</strong> No licence grants permission or fitness for medical use. See the <a href="${root}docs/disclaimer/">disclaimer</a>.</li>
  </ul>
</div>

<section aria-labelledby="which-h">
  <h2 id="which-h">1. Which licence applies to me?</h2>
  <div class="tablewrap" role="region" aria-label="Which licence applies" tabindex="0"><table>
    <thead><tr><th scope="col">I want to</th><th scope="col">What applies</th><th scope="col">Cost</th></tr></thead>
    <tbody>
      <tr><th scope="row">Read, study, teach, research, or build a pod for bench tests with water</th><td>Community licence</td><td>Free</td></tr>
      <tr><th scope="row">Improve the design and share it</th><td>Community licence (share-alike), contribution agreement</td><td>Free</td></tr>
      <tr><th scope="row">Use or extend the iOS kit (OpenPatchKit) in Trio</th><td>GPL-3.0-or-later</td><td>Free, also commercially</td></tr>
      <tr><th scope="row">Design a dock insert for another infusion set</th><td>CERN-OHL-P-2.0 (permissive)</td><td>Free, also commercially</td></tr>
      <tr><th scope="row">Manufacture, sell, rent or run a paid service based on OpenPatch</th><td>Commercial Fair-Price licence (draft)</td><td>Price cap and 5 % levy, see below</td></tr>
    </tbody></table></div>
</section>

<section aria-labelledby="com-h">
  <h2 id="com-h">2. Community licence: free for non-commercial use</h2>
  <div class="tablewrap" role="region" aria-label="Licence per path" tabindex="0"><table>
    <thead><tr><th scope="col">What</th><th scope="col">Where</th><th scope="col">Licence</th></tr></thead>
    <tbody>
      <tr><th scope="row">Hardware: CAD, PCBs, BOMs, fab packages, specification</th><td><code>mechanical/</code> <code>electronics/</code> <code>spec/</code></td><td>${L('LICENSES/CC-BY-NC-SA-4.0.txt', 'CC BY-NC-SA 4.0')}</td></tr>
      <tr><th scope="row">Documentation, images, website text</th><td><code>docs/</code> <code>*.md</code> <code>site/</code> content</td><td>${L('LICENSES/CC-BY-NC-SA-4.0.txt', 'CC BY-NC-SA 4.0')}</td></tr>
      <tr><th scope="row">Software: firmware, tools, scripts, website code</th><td><code>firmware-rs/</code> <code>firmware/</code> <code>tools/</code> <code>site/</code> code</td><td>${L('LICENSES/PolyForm-Noncommercial-1.0.0.txt', 'PolyForm Noncommercial 1.0.0')}</td></tr>
      <tr><th scope="row">Dock insert (cannula adapter) and dock interface spec</th><td><code>mechanical/op_dock.py</code> <code>dock-inserts/</code> <code>dock-coupon/</code> spec section 8a</td><td>${L('LICENSES/CERN-OHL-P-2.0.txt', 'CERN-OHL-P-2.0')}</td></tr>
      <tr><th scope="row">iOS kit (OpenPatchKit)</th><td><code>ios/</code></td><td>${L('LICENSES/GPL-3.0-or-later.txt', 'GPL-3.0-or-later')}</td></tr>
    </tbody></table></div>
  <p>Share-alike applies to hardware and documentation: derivatives carry the same licence.</p>
  <h3>Why the iOS kit is GPL</h3>
  <p>OpenPatchKit is compiled into Trio, which is AGPL-3.0. A non-commercial restriction is an extra restriction that GPL and AGPL do not allow, so a PolyForm-licensed kit could not be combined with Trio. The kit is therefore free software for everyone, including commercial users. The commercial licence does not apply to it, but does apply to everything else in a commercial product.</p>
  <h3>Why the dock insert is free for everyone</h3>
  <p>The cannula is a third-party consumable, and each manufacturer will adapt the insert to the infusion set it supports. Each manufacturer must get regulatory approval for its own adapter and infusion-set combination anyway, so the insert and the pod-side dock interface are permissively licensed and carry none of the commercial obligations (no price cap, no levy, no recoupment, no share-back). Safety obligations for the pump still apply: an insert must meet the frozen dock interface (needle alignment, dock-magnet position for the DOCKED interlock) and pass the dock-related conformance tests.</p>
</section>

<section aria-labelledby="fp-h">
  <h2 id="fp-h">3. Commercial Fair-Price licence (draft)</h2>
  <p>Anyone who manufactures, sells, rents or offers a paid or advertising-funded service based on OpenPatch needs it. The terms:</p>
  <dl class="terms">
    <dt>Price cap</dt><dd>The end-customer price (net of tax) may not exceed <strong>fully loaded unit cost plus 30 %</strong>. Unit cost covers parts, assembly, test, quality, amortised approval costs, distribution and warranty reserve, but not profit. It is a <strong>maximum, not a fixed price</strong>: selling cheaper is always allowed, and the project never sets a minimum. The licensee has the cost statement audited every year and publishes the cost breakdown per product.</dd>
    <dt>Clinical-trial levy</dt><dd><strong>5 % of net revenue</strong> goes into an open, independently administered fund for clinical studies, verification and regulatory documentation. Results it pays for are published for everyone. Until the fund exists, levies are held in escrow.</dd>
    <dt>Safety obligations</dt><dd>Keep the hardware interlock unweakened (motor only with MCU enable, watchdog latch and dock or reverse gating), the hardware step budget and the over-current cut. Keep the diagnostic code system and component-level fault reporting. Do not relax the safety limits. Pass the project's conformance suite for every release and keep the results. Report post-market faults into the shared fault catalogue. See <a href="${root}safety/">Safety</a> and <a href="${root}faults/">Fault codes</a>.</dd>
    <dt>Share-back</dt><dd>Improvements are published under the community licence, within a set period after first shipment (draft: 90 days), and safety-relevant changes before first shipment.</dd>
    <dt>Approvals and liability</dt><dd>The licensee obtains every regulatory approval itself (EU MDR, FDA or equivalent) and carries the manufacturer's responsibilities. The project gives no approval, no warranty and makes no medical claim. The licensee may not imply that the project endorses its product.</dd>
    <dt>Audit and termination</dt><dd>The project or an auditor it appoints may audit cost statements, revenue, conformance results and fault reports. Material breach, such as exceeding the cap, skipping the levy or weakening safety, can end the licence; safety breaches that endanger people end it immediately.</dd>
  </dl>
</section>

<section aria-labelledby="mv-h">
  <h2 id="mv-h">4. Money flow</h2>
  <figure class="fig wide">${flowSvg()}
  <figcaption>Followers repay the first mover out of their own capped margin. The patient price never rises because of recoupment.</figcaption></figure>
</section>

<section aria-labelledby="fm-h">
  <h2 id="fm-h">5. First-mover recoupment: why being first is not a gift to competitors</h2>
  <p>Approval and clinical trials cost millions. Without a rule, the first company pays for evidence that every follower then reuses for free, so nobody wants to be first. The draft licence fixes that:</p>
  <ol class="steps">
    <li>The first company that funds approval or trials registers as <strong>sponsor</strong> with the independent administrator, which audits the investment (only eligible, documented, external and directly attributable costs).</li>
    <li>Every <strong>other</strong> licensee that benefits pays the sponsor <strong>30 % of its gross margin per unit</strong> (draft value), via the administrator, shared pro rata.</li>
    <li>The sponsor gets back its audited investment <strong>plus at most 20 %</strong> as a first-mover return. Nothing beyond that. Money from the 5 % levy that co-funded the trials is subtracted first, so nothing is recovered twice.</li>
    <li>The obligation <strong>ends automatically</strong> when the cap is reached. The administrator publishes the status.</li>
    <li>The sponsor makes data, technical documentation and test reports available to paying followers, and publishes the results openly once recovered, or after at most 5 years (draft), whichever is earlier. Followers keep the full margin from then on.</li>
  </ol>
  <p class="note">Recoupment is paid <strong>out of the follower's capped margin</strong> and is not added to the cost basis, so the price cap stays at cost plus 30 %. The sponsor's own sales do not repay it. Recoupment never covers adapter or infusion-set approvals.</p>

  <h3>Payback calculator</h3>
  <p>Defaults are the worked example from the draft (illustrative numbers only). Change them to explore.</p>
  <form class="calc" data-calc aria-label="Recoupment calculator">
    <div class="field"><label for="c-inv">Sponsor investment (EUR)</label><input id="c-inv" type="number" inputmode="decimal" min="0" step="10000" value="2000000" data-k="inv" /></div>
    <div class="field"><label for="c-levy">Part funded by the levy fund (EUR)</label><input id="c-levy" type="number" inputmode="decimal" min="0" step="10000" value="500000" data-k="levyFunded" /></div>
    <div class="field"><label for="c-cost">Follower unit cost (EUR)</label><input id="c-cost" type="number" inputmode="decimal" min="0" step="1" value="100" data-k="cost" /></div>
    <div class="field"><label for="c-units">Follower units sold in total</label><input id="c-units" type="number" inputmode="numeric" min="0" step="1000" value="180000" data-k="units" /></div>
    <div class="field"><label for="c-share">Recoupment share of margin (%)</label><input id="c-share" type="number" inputmode="decimal" min="0" max="100" step="1" value="30" data-k="share" /></div>
    <div class="field"><label for="c-ret">First-mover return cap (%)</label><input id="c-ret" type="number" inputmode="decimal" min="0" max="100" step="1" value="20" data-k="ret" /></div>
  </form>
  <div class="calc-out" role="status" aria-live="polite" data-calc-out>
    <table><tbody>
      <tr><th scope="row">Recoverable investment (after levy funding)</th><td class="num" data-o="recov"></td></tr>
      <tr><th scope="row">Total the sponsor can recover (with return cap)</th><td class="num" data-o="total"></td></tr>
      <tr><th scope="row">Price cap per unit (cost + 30 %)</th><td class="num" data-o="price"></td></tr>
      <tr><th scope="row">Follower margin per unit</th><td class="num" data-o="margin"></td></tr>
      <tr><th scope="row">Recoupment per unit, paid out of the margin</th><td class="num" data-o="per"></td></tr>
      <tr><th scope="row">Follower keeps per unit while repaying</th><td class="num" data-o="keep"></td></tr>
      <tr><th scope="row">Levy per unit (5 % of price), goes to the fund</th><td class="num" data-o="levy"></td></tr>
      <tr><th scope="row">Collected from these units</th><td class="num" data-o="coll"></td></tr>
      <tr><th scope="row">Share of the total repaid</th><td class="num" data-o="pct"></td></tr>
      <tr><th scope="row">Follower units needed until the obligation ends</th><td class="num" data-o="need"></td></tr>
      <tr><th scope="row">Change to the patient price</th><td class="num">none (EUR 0)</td></tr>
    </tbody></table>
    <div class="bar" role="img" aria-label="Share of the sponsor's recoverable amount repaid" data-bar><span></span></div>
  </div>
</section>

<section aria-labelledby="why-h">
  <h2 id="why-h">6. Why this structure</h2>
  <p>The terms are designed so that open development is the commercially rational choice.</p>
  <ul class="plain">
    <li><strong>Be first, lose nothing.</strong> The sponsor's approval spend is a recoverable investment, not a subsidy for competitors, and the sponsor sets the reference product.</li>
    <li><strong>Followers pay fairly, patients pay little.</strong> Followers repay from their own capped margin, never through a higher end-customer price.</li>
    <li><strong>Shared evidence grows.</strong> The 5 % levy funds studies whose results are open to every licensee.</li>
    <li><strong>Improvements flow back.</strong> Share-back and post-market fault reporting keep one common, safer design instead of closed forks.</li>
  </ul>
</section>

<section aria-labelledby="legal-h">
  <h2 id="legal-h">7. Open questions for legal review</h2>
  <ul class="plain">
    <li>Price cap against EU and German competition law, and whether it can bind resellers.</li>
    <li>Compatibility of an audited price cap and levy with CC BY-NC-SA and PolyForm Noncommercial (dual licensing needs the contribution agreement).</li>
    <li>Recoupment: technology-transfer rules, Article 101 TFEU, access to clinical data and equivalence under the medical device regulation, fairness between payers.</li>
    <li>Legal form and governance of the fund, and tax treatment of the levy.</li>
    <li>Liability allocation, and whether "non-commercial" is clear enough for self-builders and researchers.</li>
  </ul>
  <p>Contributors grant the maintainer the right to also offer their contributions under the commercial licence, and the maintainer commits to keep them available under the community licence too.</p>
</section>

<section aria-labelledby="src-h">
  <h2 id="src-h">Authoritative texts on GitHub</h2>
  <ul class="linklist">
    <li>${L('LICENSE.md', 'LICENSE.md')}<span>Overview per path, dual model, third-party notes</span></li>
    <li>${L('COMMERCIAL-LICENSE.md', 'COMMERCIAL-LICENSE.md')}<span>Draft term sheet: scope, price cap, levy, recoupment, safety, term</span></li>
    <li>${L('CLA.md', 'CLA.md')}<span>Contribution agreement</span></li>
    <li>${L('CONTRIBUTING.md', 'CONTRIBUTING.md')}<span>How to contribute</span></li>
    <li>${L('DISCLAIMER.md', 'DISCLAIMER.md')}<span>Test project, never worn</span></li>
  </ul>
</section>`;
}
