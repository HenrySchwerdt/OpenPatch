// Home page: hero render, key facts as big numbers, short sections with one visual each. All numbers come from facts.mjs.
import { esc } from './lib.mjs';
import { themed } from './media.mjs';
import { SEVERITY } from './data.mjs';

const f1 = (n) => (Math.round(n * 10) / 10).toFixed(1);
export const eur = (r) => (r ? `${r.lo}–${r.hi}` : 'n/a');

/** Visual slot: themed render, or a visible placeholder when nothing exists yet. */
export function stage(g, root, { alt, sizes, eager = false, cls = '', label = 'Render pending' } = {}) {
  if (!g) return `<div class="stage ${cls}"><div class="ph"><span>${esc(label)}</span></div></div>`;
  return `<div class="stage ${cls}${g.interim ? ' is-interim' : ''}">${themed(g, root, { alt: alt ?? g.title, sizes, eager })}${g.interim ? '<span class="chip-interim" title="A photoreal render replaces this view when docs/renders/manifest.json exists">Interim CAD view</span>' : ''}</div>`;
}

function barPair(a, b) {
  const max = Math.max(a.v, b.v);
  return `<div class="barpair" role="img" aria-label="${esc(a.label)} ${f1(a.v)} millimetres, ${esc(b.label)} ${f1(b.v)} millimetres">
    <div><span class="bar-l">${esc(a.label)}</span><span class="bar-t"><i style="width:${(a.v / max) * 100}%"></i></span><span class="bar-v">${f1(a.v)}</span></div>
    <div><span class="bar-l">${esc(b.label)}</span><span class="bar-t ghost"><i style="width:${(b.v / max) * 100}%"></i></span><span class="bar-v">${f1(b.v)}</span></div></div>`;
}

export function layerStack(layers) {
  // outermost layer first
  const ordered = [...layers].reverse();
  return `<ol class="layerstack" aria-label="Safety layers, outermost first">${ordered.map((l, i) => `<li class="${/interlock/i.test(l.name) ? "key" : ""}" style="--i:${i}"><span class="ln num">${esc(l.id)}</span><span class="lt">${esc(l.name)}</span></li>`).join('')}</ol>`;
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

export function home(ctx) {
  const { root, facts: F, media, faults } = ctx;
  const hero = media.find('hero');
  const dock = media.find(/dock|cannula/i, 'detail');
  const firstStep = media.steps[0]?.image ?? null;
  const exploded = media.find('exploded');
  const nSteps = media.steps.length;

  const tiles = [];
  if (F.hero && F.dash) tiles.push(`<li class="fact"><p class="big">${f1(F.hero.h)}<span class="u">mm</span></p><h3>Thin</h3><p>${F.heightPct}% thinner than an Omnipod DASH (${f1(F.dash.h)} mm). The ${esc(F.hero.id)} measures ${f1(F.hero.l)} × ${f1(F.hero.w)} mm, ${F.volPct}% of its volume.</p>${barPair({ label: 'OpenPatch', v: F.hero.h }, { label: 'DASH', v: F.dash.h })}</li>`);
  if (F.uPerStep) tiles.push(`<li class="fact"><p class="big">${esc(F.uPerStep)}<span class="u">U/step</span></p><h3>Fine dosing</h3><p>One motor step moves ${esc(F.uPerStep)} U. The ${F.gear.motor} T : ${F.gear.screw} T gear pair gives about ${F.stepsFor005.toFixed(1)} steps for the smallest 0.05 U dose.</p></li>`);
  if (F.layers.length) tiles.push(`<li class="fact"><p class="big">${F.layers.length}<span class="u">layers</span></p><h3>Defence in depth</h3><p>One hardware interlock the firmware cannot override, backed by ${F.layers.length - 1} more independent layers.</p></li>`);
  if (F.cost?.next) tiles.push(`<li class="fact"><p class="big">${eur(F.cost.next)}<span class="u">€</span></p><h3>Per extra bench pump</h3><p>First pump ${eur(F.cost.first)} € all in, so the ${esc(F.cost.target)} € target is not reached yet. Planning estimates, not quotes.</p></li>`);

  const sim = F.sim;
  const lic = F.licence;
  return `
<section class="hero" aria-labelledby="h1">
  <div class="wrap hero-copy">
    <p class="eyebrow">Open test platform · Rev A bench pod</p>
    <h1 id="h1">A patch pump,<br>drawn in the open.</h1>
    <p class="lede">OpenPatch is a fully published design for a flat, detachable pump. Every dimension, safety limit and fault code is public. It is built and tested on a bench with water, and nowhere else.</p>
    <p class="cta"><a class="btn primary" href="${root}design/">Explore the product</a><a class="btn" href="${root}build/">Follow the build</a></p>
  </div>
  <div class="wrap hero-stage">${stage(hero, root, { alt: 'OpenPatch OP-100 bench pod', sizes: '(min-width: 1240px) 1160px, 100vw', eager: true, cls: 'hero-img' })}</div>
</section>

<section class="wrap facts" aria-label="Key facts"><ul class="factgrid">${tiles.join('')}</ul>
${F.sizes.length ? `<p class="factnote">Sizes ${F.sizes.map((s) => `${esc(s.id)} ${f1(s.l)} × ${f1(s.w)} × ${f1(s.h)} mm (${s.ml} ml)`).join(' · ')}. Read from the generated CAD data.</p>` : ''}</section>

<section class="wrap feature" aria-labelledby="f-safe">
  <div class="feature-copy">
    <p class="eyebrow">Safety architecture</p>
    <h2 id="f-safe">Safe by hardware, not by promise.</h2>
    <p>The motor supply is switched by logic that the firmware cannot override: no enable, no watchdog, no dock, no motion. ${F.layers.length ? `${F.layers.length} independent layers catch what the one before misses.` : ''}</p>
    <p class="chiprow"><span class="formula">${esc(F.interlock).replace(/ AND /g, ' <b>AND</b> ').replace(/ OR /g, ' <b>OR</b> ')}</span></p>
    <p class="more"><a class="arrow" href="${root}safety/">See the interlock simulator</a></p>
  </div>
  <div class="feature-visual">${layerStack(F.layers)}</div>
</section>

<section class="wrap feature flip" aria-labelledby="f-dock">
  <div class="feature-copy">
    <p class="eyebrow">Modular dock</p>
    <h2 id="f-dock">Swap the dock, not the pump.</h2>
    <p>The pod meets the cannula through one small printed insert on a frozen interface. A different infusion set needs a different insert, never a different pump. Inserts are permissively licensed.</p>
    <p class="more"><a class="arrow" href="${root}design/#dock">How the dock works</a></p>
  </div>
  <div class="feature-visual">${stage(dock, root, { alt: dock?.title ?? 'Cannula dock section', sizes: '(min-width: 900px) 560px, 100vw', label: 'Dock render pending' })}</div>
</section>

<section class="wrap feature" aria-labelledby="f-fault">
  <div class="feature-copy">
    <p class="eyebrow">Open fault codes</p>
    <h2 id="f-fault">${faults ? `${faults.total} ways to fail, all named.` : 'Every fault, named.'}</h2>
    <p>Every anomaly gets a code, a severity, the replaceable part and the text the app would show. The catalogue is the single source for firmware, protocol and app.</p>
    <p class="more"><a class="arrow" href="${root}faults/">Search the catalogue</a></p>
  </div>
  <div class="feature-visual">${faultSamples(faults)}</div>
</section>

<section class="wrap feature flip" aria-labelledby="f-sim">
  <div class="feature-copy">
    <p class="eyebrow">Simulation</p>
    <h2 id="f-sim">Break it on screen first.</h2>
    <p>${sim ? `The CAD is checked by ${sim.total} simulated requirements. ${sim.pass} pass, ${sim.warn} are warnings and ${sim.fail} fail. The failures are published and they decide what gets fixed before any part is ordered.` : 'The simulation report was not found at build time.'}</p>
    <p class="more"><a class="arrow" href="${root}docs/mechanical-sim-report/">Read the simulation report</a></p>
  </div>
  <div class="feature-visual">${sim ? `<div class="simcard" role="img" aria-label="${sim.pass} pass, ${sim.warn} warning, ${sim.fail} fail"><div class="simbar"><i class="s-pass" style="flex:${sim.pass}"></i><i class="s-warn" style="flex:${sim.warn}"></i><i class="s-fail" style="flex:${sim.fail}"></i></div>
    <dl class="simkey"><div><dt><span class="dot s-pass"></span>Pass</dt><dd class="num">${sim.pass}</dd></div><div><dt><span class="dot s-warn"></span>Warn</dt><dd class="num">${sim.warn}</dd></div><div><dt><span class="dot s-fail"></span>Fail</dt><dd class="num">${sim.fail}</dd></div></dl>
    <p class="simnote">Not a validation. Many rows rest on stated assumptions that bench tests must confirm.</p></div>` : ''}</div>
</section>

<section class="wrap feature" aria-labelledby="f-build">
  <div class="feature-copy">
    <p class="eyebrow">Build</p>
    <h2 id="f-build">No soldering iron.</h2>
    <p>${nSteps ? `${nSteps} illustrated steps` : 'Illustrated steps'} with parts and tools for each one. Tweezers, a small screwdriver and patience. The boards arrive assembled.</p>
    <p class="more"><a class="arrow" href="${root}build/">Open the build guide</a></p>
  </div>
  <div class="feature-visual">${stage(firstStep ?? exploded, root, { alt: 'First build step', sizes: '(min-width: 900px) 560px, 100vw', label: 'Build images pending' })}</div>
</section>

<section class="wrap feature flip" aria-labelledby="f-lic">
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
