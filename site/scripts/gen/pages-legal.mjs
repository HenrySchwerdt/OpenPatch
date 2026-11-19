// Disclaimers, privacy and legal notice page.
import { blobUrl, REPO_URL } from './lib.mjs';

export function legal({ root }) {
  const G = (p, t) => `<a href="${blobUrl(p)}">${t ?? p}</a>`;
  return `
<header class="pagehead">
  <p class="kicker">Disclaimers and legal</p>
  <h1>Disclaimers, privacy and legal notice</h1>
  <p class="lede">Read this before anything else on this site. It applies to every page, every document, every file in the repository and every model shown here.</p>
</header>

<section class="danger" aria-labelledby="d1">
  <h2 id="d1">1. Not a medical device</h2>
  <ul>
    <li>OpenPatch is <strong>not a medical device</strong>. It is not approved, certified, cleared or validated in any market: no CE marking, no FDA clearance, no approval by any other authority.</li>
    <li>It is an experimental engineering test project. It has none of the risk management, software validation, biocompatibility testing, clinical evaluation or quality system that a real insulin pump requires.</li>
    <li>Over-delivery of insulin causes severe hypoglycaemia. Under-delivery or interruption causes diabetic ketoacidosis. Either can kill.</li>
  </ul>
</section>

<section class="danger" aria-labelledby="d2">
  <h2 id="d2">2. Never on a person or animal. Never insulin or any drug. Water only.</h2>
  <ul>
    <li><strong>Never</strong> wear it, attach it to a person or animal, or connect it to a cannula in a body.</li>
    <li><strong>Never</strong> fill it with insulin or any other drug: not even expired insulin, not even into a container. All bench tests described anywhere in this project use <strong>water only</strong>, delivered into a vial, beaker or onto a precision balance on a table, never through a cannula inserted in a body.</li>
    <li>Nothing on this site describes, and nothing on this site may be read as describing, on-body use. There are no such instructions and there will be none.</li>
    <li>The phone integration (Trio and LoopKit kit) exists to exercise the communication protocol against a pod on a bench, never to dose a person.</li>
  </ul>
</section>

<section aria-labelledby="d3">
  <h2 id="d3">3. No medical advice</h2>
  <p>Nothing here is medical advice. If you live with diabetes, talk to your diabetes care team, use an approved device, and <strong>do not change your therapy because of anything you read on this site</strong>. If you need an insulin pump, use one that a regulator has approved.</p>
</section>

<section aria-labelledby="d4">
  <h2 id="d4">4. No warranty, no liability, your own responsibility</h2>
  <ul class="plain">
    <li>Everything is provided "as is", without warranty of any kind, and without liability of the authors or the maintainer to the extent the law allows.</li>
    <li>You use anything from this project at your own risk. Building, ordering, machining, soldering, flashing or powering anything described here is entirely your own responsibility, including hazards from batteries, tools, chemicals and electricity.</li>
    <li>The content may be wrong or incomplete. Designs are unverified. Parts are modelled as simplified envelopes, many values are estimates, and some results come from simulation, not from hardware. The <a href="${root}status/">status board</a> says what has and has not been verified.</li>
  </ul>
</section>

<section aria-labelledby="d5">
  <h2 id="d5">5. Drafts: regulatory documents and the commercial licence</h2>
  <p>Documents under <code>regulatory/</code> in the repository and the commercial "Fair-Price" licence are <strong>drafts</strong>. They are neither legal advice nor regulatory advice, and they do not make the project, or anything built from it, compliant with any law or standard. See the <a href="${root}licence/">licence page</a> and ${G('LICENSE.md', 'LICENSE.md')}.</p>
</section>

<section aria-labelledby="d6">
  <h2 id="d6">6. Trademarks and independence</h2>
  <ul class="plain">
    <li>Accu-Chek and Insight Flex are trademarks of Roche. Omnipod and DASH are trademarks of Insulet. Trio and LoopKit belong to their respective projects and owners. All other names belong to their owners.</li>
    <li>They are named only to describe compatibility. There is <strong>no affiliation with, sponsorship by or endorsement from</strong> any of them.</li>
    <li>Do-it-yourself and community diabetes technology is not endorsed by any device manufacturer. Using it may void warranties and support, and may be unlawful for medical use in your country.</li>
  </ul>
</section>

<section aria-labelledby="d7">
  <h2 id="d7">7. Security research</h2>
  <p>If you find a security problem in the design, firmware or protocol, please report it through coordinated disclosure as described in ${G('SECURITY.md', 'SECURITY.md')} before publishing details. Do not attack, probe or interfere with devices, accounts or networks you do not own or have permission to test.</p>
</section>

<section aria-labelledby="d8">
  <h2 id="d8">8. Licence summary</h2>
  <p>Free for non-commercial study, research and bench self-builds (CC BY-NC-SA 4.0 for hardware and documentation, PolyForm Noncommercial 1.0.0 for software, GPL-3.0-or-later for the iOS kit, CERN-OHL-P-2.0 for the dock insert). Commercial use needs a separate licence, currently a draft. The project is source-available, not open source in the strict sense. Details: <a href="${root}licence/">Licence and fair-price model</a>.</p>
</section>

<section aria-labelledby="d9">
  <h2 id="d9">9. Privacy</h2>
  <ul class="plain">
    <li>This site sets <strong>no cookies</strong>, runs <strong>no analytics or tracking</strong>, and has no forms, accounts or comments.</li>
    <li>All fonts, scripts, styles, images and 3D models are <strong>served from the site itself</strong>. The pages load nothing from Google Fonts, CDNs or other third parties. A content security policy enforces this.</li>
    <li>The only data stored in your browser is your colour theme choice (<code>localStorage</code>, key <code>op-theme</code>), and only if you change it. It never leaves your device.</li>
    <li>The site is hosted on <strong>GitHub Pages</strong>. GitHub, as the host, may log IP addresses and request data when you visit. See <a href="https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement" rel="noopener">GitHub's privacy statement</a>. Links to GitHub and other external sites are ordinary links; those sites have their own privacy policies.</li>
  </ul>
</section>

<section aria-labelledby="d10">
  <h2 id="d10">10. Who is behind this</h2>
  <p>OpenPatch is a private, non-commercial engineering project. Nothing is sold, and the site earns nothing. It is maintained as "the OpenPatch maintainer" and "the project". The source repository is <a href="${REPO_URL}">on GitHub</a>. Full repository disclaimer: <a href="${root}docs/disclaimer/">DISCLAIMER.md</a>.</p>
</section>`;
}
