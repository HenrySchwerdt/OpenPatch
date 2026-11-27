// Home page: the pump family (one card per model) above the fold, a side-by-side comparison, then short shared sections with one
// visual each. Numbers come from facts.mjs (OpenPatch) and facts-opentube.mjs (OpenTube).
import { esc } from './lib.mjs';
import { stage } from './media.mjs';
import { SEVERITY } from './data.mjs';
import { modelCard, models } from './family.mjs';

const f1 = (n) => (Math.round(n * 10) / 10).toFixed(1);
export const eur = (r) => (r ? `${r.lo}–${r.hi}` : 'n/a');
export { stage };

/** Two horizontal bars to one scale. unit is spoken in the label (e.g. "millimetres"). */
export function barPair(a, b, unit = 'millimetres') {
  const max = Math.max(a.v, b.v);
  return `<div class="barpair" role="img" aria-label="${esc(a.label)} ${f1(a.v)} ${unit}, ${esc(b.label)} ${f1(b.v)} ${unit}">
    <div><span class="bar-l">${esc(a.label)}</span><span class="bar-t"><i style="width:${(a.v / max) * 100}%"></i></span><span class="bar-v">${f1(a.v)}</span></div>
    <div><span class="bar-l">${esc(b.label)}</span><span class="bar-t ghost"><i style="width:${(b.v / max) * 100}%"></i></span><span class="bar-v">${f1(b.v)}</span></div></div>`;
}

/** Interlock formula with its operators set in bold. */
export function formula(s) {
  return `<span class="formula">${esc(s).replace(/ (AND|OR|XOR) /g, ' <b>$1</b> ')}</span>`;
}

export function layerStack(layers) {
  // outermost layer first
  const ordered = [...layers].reverse();
  return `<ol class="layerstack" aria-label="Safety layers, outermost first">${ordered.map((l, i) => `<li class="${/interlock/i.test(l.name) ? "key" : ""}" style="--i:${i}"><span class="ln num">${esc(l.id)}</span><span class="lt">${esc(l.name)}</span></li>`).join('')}</ol>`;
}

/** OpenPatch key facts as big numbers (shown on the OpenPatch product page). */
export function openPatchFacts(F) {
  const tiles = [];
  if (F.hero && F.dash) tiles.push(`<li class="fact"><p class="big">${f1(F.hero.h)}<span class="u">mm</span></p><h3>Thin</h3><p>${F.heightPct}% thinner than an Omnipod DASH (${f1(F.dash.h)} mm). The ${esc(F.hero.id)} measures ${f1(F.hero.l)} × ${f1(F.hero.w)} mm, ${F.volPct}% of its volume.</p>${barPair({ label: 'OpenPatch', v: F.hero.h }, { label: 'DASH', v: F.dash.h })}</li>`);
  if (F.uPerStep) tiles.push(`<li class="fact"><p class="big">${esc(F.uPerStep)}<span class="u">U/step</span></p><h3>Fine dosing</h3><p>One motor step moves ${esc(F.uPerStep)} U. The ${F.gear.motor} T : ${F.gear.screw} T gear pair gives about ${F.stepsFor005.toFixed(1)} steps for the smallest 0.05 U dose.</p></li>`);
  if (F.layers.length) tiles.push(`<li class="fact"><p class="big">${F.layers.length}<span class="u">layers</span></p><h3>Defence in depth</h3><p>One hardware interlock the firmware cannot override, backed by ${F.layers.length - 1} more independent layers.</p></li>`);
  if (F.cost?.next) tiles.push(`<li class="fact"><p class="big">${eur(F.cost.next)}<span class="u">€</span></p><h3>Per extra bench pump</h3><p>First pump ${eur(F.cost.first)} € all in, so the ${esc(F.cost.target)} € target is not reached yet. Planning estimates, not quotes.</p></li>`);
  if (!tiles.length) return '';
  return `<ul class="factgrid">${tiles.join('')}</ul>
${F.sizes.length ? `<p class="factnote">Sizes ${F.sizes.map((s) => `${esc(s.id)} ${f1(s.l)} × ${f1(s.w)} × ${f1(s.h)} mm (${s.ml} ml)`).join(' · ')}. Read from the generated CAD data.</p>` : ''}`;
}

function faultSamples(faults) {
  if (!faults) return '';
  const pick = [];
  for (const sev of ['L', 'F', 'W']) {
    const c = faults.codes.find((x) => x.sev === sev && x.fruName && x.trio);
    if (c) pick.push(c);
  }
  return `<div class="faultmock" aria-label="Three example fault codes from the catalogue">${pick.map((c) => `<div class="fm sev-${c.sev}"><div class="fm-top"><span class="num code">${esc(c.code)}</span><span class="pill sev-${c.sev}">${SEVERITY[c.sev].label}</span></div><p class="fm-name">${esc(c.name)}</p><p class="fm-part"><span>Replace</span> ${esc(c.fruName)}</p><p class="fm-trio">“${esc(c.trio)}”</p></div>`).join('')}</div>`;
}

/** Side-by-side table of both models; every cell from the facts. */
function compare(F, T, root) {
  const h = F.hero;
  const na = 'n/a';
  const rows = [
    ['Reservoir', F.sizes.length ? `Stadium bore 16 × 5 mm: ${F.sizes.map((s) => s.ml).join(' / ')} ml (${F.sizes.map((s) => s.id).join(', ')})` : na,
      T.cart ? `${f1(T.cart.ml)} ml glass cartridge, ${esc(T.cart.iso ?? '')}${T.deliverable ? `; ${T.deliverable} ml deliverable` : ''}` : na],
    ['Size', h ? `${esc(h.id)}: ${f1(h.l)} × ${f1(h.w)} × ${f1(h.h)} mm` : na,
      T.size ? `${f1(T.size.l)} × ${T.size.w} × ${T.size.h} mm with the adapter` : na],
    ['Fluid connection', 'Needle in a swappable printed dock insert',
      'Original Accu-Chek Insight Adapter &amp; Tubing as the front cap; a mylife YpsoPump adapter is planned'],
    ['Drive', F.motor && F.gear ? `${esc(F.motor)} stepper, ${F.gear.motor} T : ${F.gear.screw} T gears, M1.6 leadscrew` : na,
      T.drive ? `${esc(T.drive.motor ?? '')} gearmotor, z${T.drive.pinion} : z${T.drive.gear} gears, ${esc(T.drive.screw ?? '')} screw beside the cartridge, push stem into it` : na],
    ['Ready to advance when', 'the pod is docked: a hall sensor reads the dock magnet',
      'the adapter is locked: a steel ball, a pin and a detector switch'],
    ['Hardware interlock', formula(F.interlock), T.interlock ? formula(T.interlock) : na],
    ['Status', `Rev A bench pod. <a href="${root}status/">Project status</a>`, 'v2 print parts in fit testing, main board being routed. Nothing verified on the bench yet.'],
  ];
  // explicit roles keep the table semantics when the narrow layout restyles rows as cards (display: grid / block)
  const shared = T.chips?.length ? `<tr class="shared" role="row"><th scope="row" role="rowheader">Electronics</th><td colspan="2" role="cell">One chip set for both: ${esc(T.chips.join(', '))}.</td></tr>` : '';
  return `<div class="tablewrap compare" role="region" aria-label="OpenPatch and OpenTube compared" tabindex="0"><table role="table">
  <thead role="rowgroup"><tr role="row"><th scope="col" role="columnheader"><span class="sr">Property</span></th><th scope="col" role="columnheader"><a href="${root}design/">OpenPatch</a></th><th scope="col" role="columnheader"><a href="${root}opentube/">OpenTube</a></th></tr></thead>
  <tbody role="rowgroup">${rows.map(([k, a, b]) => `<tr role="row"><th scope="row" role="rowheader">${k}</th><td role="cell" data-model="OpenPatch">${a}</td><td role="cell" data-model="OpenTube">${b}</td></tr>`).join('')}${shared}</tbody></table></div>`;
}

export function home(ctx) {
  const { root, facts: F, media, faults, ot: T } = ctx;
  const firstStep = media.steps[0]?.image ?? null;
  const exploded = media.find('exploded');
  const nSteps = media.steps.length;
  const fam = models(media, F, T);
  const sim = F.sim;
  const lic = F.licence;
  return `
<section class="famhero" aria-labelledby="h1">
  <div class="wrap famhero-head">
    <div>
      <p class="eyebrow">The OpenPatch project · two open test platforms</p>
      <h1 id="h1">Two pumps,<br>drawn in the open.</h1>
    </div>
    <p class="lede">A flat patch pump and a tubed cartridge pump on one electronics design and one hardware interlock. Every dimension, safety limit and fault code is public. Both are built and tested on a bench, with water, and nowhere else.</p>
  </div>
  <div class="wrap models">${fam.map((m, i) => modelCard(m, root, { eager: i === 0 })).join('')}</div>
</section>

<section class="wrap block compare-block" aria-labelledby="cmp-h">
  <p class="eyebrow">Side by side</p>
  <h2 id="cmp-h">One electronics design, two ways to hold the water.</h2>
  ${compare(F, T, root)}
  <p class="note">OpenPatch values from the generated CAD data and spec sections 4 and 7a; OpenTube values from <span class="num">mechanical/out/cart_a_v2/package_report.json</span> and the <a href="${root}docs/mechanical-cart-a-v2-brief/">OpenTube design brief</a>.</p>
</section>

<section class="wrap feature" aria-labelledby="f-safe">
  <div class="feature-copy">
    <p class="eyebrow">Safety architecture</p>
    <h2 id="f-safe">Safe by hardware, not by promise.</h2>
    <p>In both pumps the motor supply is switched by logic that the firmware cannot override: no enable, no watchdog, no docked pod or locked adapter, no forward motion.${F.layers.length ? ` In OpenPatch, ${F.layers.length} independent layers catch what the one before misses.` : ''}</p>
    <p class="chiprow"><span class="formula-label">OpenPatch</span>${formula(F.interlock)}</p>
    ${T.interlock ? `<p class="chiprow"><span class="formula-label">OpenTube</span>${formula(T.interlock)}</p>` : ''}
    <p class="more"><a class="arrow" href="${root}safety/">See the interlock simulator</a></p>
  </div>
  <div class="feature-visual">${layerStack(F.layers)}</div>
</section>

<section class="wrap feature flip" aria-labelledby="f-fault">
  <div class="feature-copy">
    <p class="eyebrow">Open fault codes</p>
    <h2 id="f-fault">${faults ? `${faults.total} ways to fail, all named.` : 'Every fault, named.'}</h2>
    <p>Every anomaly gets a code, a severity, the replaceable part and the text the app would show. The catalogue is the single source for firmware, protocol and app.</p>
    <p class="more"><a class="arrow" href="${root}faults/">Search the catalogue</a></p>
  </div>
  <div class="feature-visual">${faultSamples(faults)}</div>
</section>

<section class="wrap feature" aria-labelledby="f-sim">
  <div class="feature-copy">
    <p class="eyebrow">Simulation · OpenPatch</p>
    <h2 id="f-sim">Break it on screen first.</h2>
    <p>${sim ? `The OpenPatch CAD is checked by ${sim.total} simulated requirements. ${sim.pass} pass, ${sim.warn} are warnings and ${sim.fail} fail. The failures are published and they decide what gets fixed before any part is ordered.` : 'The simulation report was not found at build time.'}</p>
    <p class="more"><a class="arrow" href="${root}docs/mechanical-sim-report/">Read the simulation report</a></p>
  </div>
  <div class="feature-visual">${sim ? `<div class="simcard" role="img" aria-label="${sim.pass} pass, ${sim.warn} warning, ${sim.fail} fail"><div class="simbar"><i class="s-pass" style="flex:${sim.pass}"></i><i class="s-warn" style="flex:${sim.warn}"></i><i class="s-fail" style="flex:${sim.fail}"></i></div>
    <dl class="simkey"><div><dt><span class="dot s-pass"></span>Pass</dt><dd class="num">${sim.pass}</dd></div><div><dt><span class="dot s-warn"></span>Warn</dt><dd class="num">${sim.warn}</dd></div><div><dt><span class="dot s-fail"></span>Fail</dt><dd class="num">${sim.fail}</dd></div></dl>
    <p class="simnote">Not a validation. Many rows rest on stated assumptions that bench tests must confirm.</p></div>` : ''}</div>
</section>

<section class="wrap feature flip" aria-labelledby="f-build">
  <div class="feature-copy">
    <p class="eyebrow">Build · OpenPatch</p>
    <h2 id="f-build">No soldering iron.</h2>
    <p>${nSteps ? `${nSteps} illustrated steps` : 'Illustrated steps'} for the OpenPatch bench pod, with parts and tools for each one. Tweezers, a small screwdriver and patience. The boards arrive assembled. OpenTube is designed to the same rule.</p>
    <p class="more"><a class="arrow" href="${root}build/">Open the build guide</a></p>
  </div>
  <div class="feature-visual">${stage(firstStep ?? exploded, root, { alt: 'First build step', sizes: '(min-width: 900px) 560px, 100vw', label: 'Build images pending' })}</div>
</section>

<section class="wrap feature" aria-labelledby="f-lic">
  <div class="feature-copy">
    <p class="eyebrow">Fair licence</p>
    <h2 id="f-lic">Free to build. Fair to sell.</h2>
    <p>Free for study, research and bench builds. Anyone who sells a product based on it signs a fair-price licence. It is a draft under legal review, and it is source-available rather than open source.</p>
    <p class="more"><a class="arrow" href="${root}licence/">Licence and payback calculator</a></p>
  </div>
  <div class="feature-visual">${lic ? `<div class="licard"><div><p class="big sm">≤ cost + ${esc(lic.cap)}<span class="u">%</span></p><p>Maximum price of a product, audited every year.</p></div><div><p class="big sm">${esc(lic.levy)}<span class="u">%</span></p><p>Of net revenue into an open clinical-trial fund.</p></div><div><p class="big sm">+${esc(lic.ret)}<span class="u">%</span></p><p>Cap on the first mover’s return, then the data go public.</p></div></div>` : ''}</div>
</section>

<section class="wrap closer" aria-labelledby="f-end">
  <h2 id="f-end">Read it. Build it on a bench. Break it.</h2>
  <p>Status is public, including what is not verified yet.</p>
  <p class="cta"><a class="btn primary" href="${root}status/">See the status</a><a class="btn" href="${root}docs/">Browse the docs</a></p>
</section>`;
}
