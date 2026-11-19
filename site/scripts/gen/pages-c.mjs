// Build guide index, Parts and cost, Docs index and rendered document pages.
import { blobUrl, esc, inline, read, section } from './lib.mjs';
import { docUrl } from './docs.mjs';

const BADGE = { locked: ['Locked', 'locked'], sample: ['Lock after sample', 'sample'], candidate: ['Candidate', 'candidate'] };

export function build(ctx) {
  const { root, reg } = ctx;
  const link = (path, label) => { const e = reg.find((x) => x.path === path); return e ? `<a href="${docUrl(e, root)}">${esc(label)}</a>` : `<span class="muted">${esc(label)} (not written yet)</span>`; };
  const steps = [
    ['Read the disclaimer and the safety concept', 'Nothing in these guides is for use on a person. Water goes into containers.', `${link('DISCLAIMER.md', 'Disclaimer')} · ${link('docs/02-safety.md', 'Safety concept')}`],
    ['Set up the tools', 'CAD, KiCad, Rust, Node and optional tools. No soldering iron is needed for the pod itself.', link('docs/SETUP.md', 'Developer setup')],
    ['Buy a sample set first', 'Every part marked "lock after sample" or "candidate" is measured on a bought sample before CAD and boards are frozen.', `${link('docs/PARTS-LOCK.md', 'Parts lock list')} · <a href="${root}parts/">Parts and cost</a>`],
    ['Order one bench iteration', 'Boards (JLCPCB), prints (JLC3DP), CNC reservoir (PCBWay), motor, gears, small parts.', link('docs/SHOPPING.md', 'Shopping list')],
    ['Print and test the cannula dock coupon', 'The Insight Flex head dimensions are not public. Print the six-variant coupon and fit it to a real head before anything else.', link('mechanical/cannula-measurement.md', 'Cannula measurement sheet')],
    ['Assemble the pod', 'Tweezers, small screwdriver, UV lamp. No soldering, no glue (two exceptions are listed).', link('mechanical/ASSEMBLY.md', 'Assembly sequence')],
    ['Fill by draw mode (water)', 'The app selects an amount, the motor retracts and draws it in through the septum.', link('mechanical/REFILL.md', 'Refill procedure')],
    ['Flash the controller and run the bench tests', 'Gravimetric accuracy, occlusion, endurance, fault injection. Water only, into a vial on a balance.', `${link('firmware-rs/docs/bench-testing.md', 'Firmware bench testing')} · <a href="${root}safety/#bench-h">Verification plan</a>`],
  ];
  const guides = reg.filter((e) => e.group === 'Build and order');
  return `
<header class="pagehead">
  <p class="kicker">Build</p>
  <h1>Build guides: from order to bench test</h1>
  <p class="lede">A bench build of the Rev A pod. Every step links to the document it comes from, so nothing on this page is a second source of truth.</p>
</header>
<div class="callout danger-note" role="note"><p><strong>Bench only.</strong> The finished device is never worn and never connected to a cannula in a person. These guides stop at a pod on a table delivering water into a container.</p></div>
<div class="callout" role="note"><p><strong>Not yet validated by a physical build.</strong> No order has been placed yet, so none of these procedures has been followed end to end on real parts. Expect corrections; see <a href="${root}status/">status</a>.</p></div>
<ol class="steps big">${steps.map(([t, d, l]) => `<li><h2>${esc(t)}</h2><p>${esc(d)}</p><p class="links">${l}</p></li>`).join('')}</ol>
<section aria-labelledby="all-h"><h2 id="all-h">All build documents</h2>
<ul class="linklist">${guides.map((e) => `<li><a href="${docUrl(e, root)}"><strong>${esc(e.title)}</strong></a><span class="num">${esc(e.path)}</span></li>`).join('')}</ul></section>`;
}

export function parts(ctx) {
  const { root, parts: P, md, reg } = ctx;
  const d = (p) => { const e = reg.find((x) => x.path === p); return e ? docUrl(e, root) : blobUrl(p); };
  const shop = read('docs/SHOPPING.md') ?? '';
  const cost = read('docs/05-cost-model.md') ?? '';
  const rows = (P ?? []).map((p) => { const [lab, k] = BADGE[p.statusKey]; return `<tr data-status="${p.statusKey}"><th scope="row" class="num">${esc(p.no)}</th><td>${esc(p.fn)}</td><td>${inline(p.part)}</td><td>${esc(p.source)}</td><td class="num">${esc(p.price)}</td><td><span class="badge st-${k}">${lab}</span></td><td class="why">${inline(p.why).slice(0, 600)}</td></tr>`; }).join('');
  const n = { locked: 0, sample: 0, candidate: 0 };
  for (const p of P ?? []) n[p.statusKey]++;
  return `
<header class="pagehead">
  <p class="kicker">Parts and cost</p>
  <h1>Bought-in parts and what a pump costs</h1>
  <p class="lede">Every external part, with chosen part, source, price and lock status. Prices are planning estimates until real invoices are logged in the <a href="${d('docs/05-cost-model.md')}">cost model</a>.</p>
</header>
<section aria-labelledby="pl-h">
  <h2 id="pl-h">Parts lock list</h2>
  ${P ? `<p class="muted">${P.length} parts: ${n.locked} locked, ${n.sample} lock after sample, ${n.candidate} candidate. Source: <a href="${d('docs/PARTS-LOCK.md')}">docs/PARTS-LOCK.md</a>.</p>
  <div class="chips" role="group" aria-label="Filter by status" data-filter-group="status">
    <button type="button" class="chip" data-filter="" aria-pressed="true">All</button>
    <button type="button" class="chip" data-filter="locked" aria-pressed="false">Locked</button>
    <button type="button" class="chip" data-filter="sample" aria-pressed="false">Lock after sample</button>
    <button type="button" class="chip" data-filter="candidate" aria-pressed="false">Candidate</button>
  </div>
  <div class="tablewrap" role="region" aria-label="Parts lock list" tabindex="0"><table class="parts" data-filter-table="status">
    <thead><tr><th scope="col">#</th><th scope="col">Function</th><th scope="col">Chosen part</th><th scope="col">Source</th><th scope="col">Price</th><th scope="col">Status</th><th scope="col">Notes</th></tr></thead><tbody>${rows}</tbody></table></div>
  <p class="note"><strong>Locked</strong>: dimensions from a datasheet. <strong>Lock after sample</strong>: chosen, but measured on a bought sample before CAD is frozen. <strong>Candidate</strong>: no verified listing yet.</p>` : '<p class="callout warn">docs/PARTS-LOCK.md not found at build time.</p>'}
</section>
<section aria-labelledby="cost-h" id="cost">
  <h2 id="cost-h">Cost per pump</h2>
  <p>Estimates, in EUR (shopping study, all-in for one builder in Germany including shipping, VAT and duty) and USD (cost model). Ranges, not quotes.</p>
  ${shop ? `<div class="md">${md(section(shop, /^0\.1/))}</div><h3>Marginal additional pump</h3><div class="md">${md(section(shop, /^0\.4/))}</div>` : ''}
  ${cost ? `<h3>One bench iteration (Rev A)</h3><div class="md">${md(section(cost, /^One bench iteration/))}</div><h3>Final design (Rev B), small quantity</h3><div class="md">${md(section(cost, /^Final design/))}</div>` : ''}
  <p class="note">Line items and sources: <a href="${d('docs/SHOPPING.md')}">shopping list</a>. Price log: <a href="${d('docs/05-cost-model.md')}#price-log-fill-in-after-each-order">cost model</a>, empty until the first order.</p>
</section>`;
}

export function docsIndex(ctx) {
  const { root, reg } = ctx;
  const groups = [...new Set(reg.map((e) => e.group))];
  return `
<header class="pagehead">
  <p class="kicker">Docs</p>
  <h1>Documentation library</h1>
  <p class="lede">${reg.length} documents from the repository, rendered at build time. Each page links back to its source file on GitHub; the repository is the single source of truth.</p>
</header>
${groups.map((g) => `<section><h2>${esc(g)}</h2><ul class="linklist">${reg.filter((e) => e.group === g).map((e) => `<li><a href="${docUrl(e, root)}"><strong>${esc(e.title)}</strong></a><span class="num">${esc(e.path)}</span></li>`).join('')}</ul></section>`).join('')}`;
}

export function docPage(ctx, entry, rendered) {
  const { root } = ctx;
  const toc = rendered.toc.filter((t) => t.depth === 2);
  return `
<header class="pagehead">
  <p class="kicker"><a href="${root}docs/">Docs</a> · ${esc(entry.group)}</p>
  <h1>${esc(entry.title)}</h1>
  <p class="srcline"><span class="num">${esc(entry.path)}</span> · <a href="${blobUrl(entry.path)}">View or edit on GitHub</a></p>
</header>
<div class="docwrap">
  ${toc.length > 2 ? `<nav class="toc" aria-label="On this page"><details open><summary>On this page</summary><ol>${rendered.toc.map((t) => `<li class="d${t.depth}"><a href="#${t.id}">${esc(t.text)}</a></li>`).join('')}</ol></details></nav>` : ''}
  <article class="md doc">${rendered.html}</article>
</div>`;
}
