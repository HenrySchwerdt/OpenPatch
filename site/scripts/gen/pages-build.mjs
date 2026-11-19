// Build page: interactive step viewer (docs/build-guide/steps.json, interim: mechanical/ASSEMBLY.md), then the order path.
import { esc } from './lib.mjs';
import { docUrl } from './docs.mjs';
import { stage } from './pages-home.mjs';
import { themed } from './media.mjs';

function badge(item, kind, root = '') {
  const n = typeof item === 'string' ? { name: item } : item;
  return `<li class="tag ${kind}">${n.img ? `<span class="tagimg">${themed(n.img, root, { alt: '', sizes: '48px' })}</span>` : ''}<span>${n.qty ? `<b class="num">${esc(n.qty)}×</b> ` : ''}${esc(n.name)}</span></li>`;
}

export function build(ctx) {
  const { root, reg, media } = ctx;
  const steps = media.steps;
  const link = (path, label) => { const e = reg.find((x) => x.path === path); return e ? `<a href="${docUrl(e, root)}">${esc(label)}</a>` : `<span class="muted">${esc(label)} (not written yet)</span>`; };
  const tools = [...new Map(steps.flatMap((s) => s.tools).map((t) => [typeof t === 'string' ? t : t.name, t])).values()];
  const guides = reg.filter((e) => e.group === 'Build and order');

  const stepHtml = steps.map((s, i) => `
<article class="step" id="step-${esc(s.id)}" data-step="${i}" aria-labelledby="st-${esc(s.id)}">
  <div class="step-media">${stage(s.image, root, { alt: s.image?.title ?? s.title, sizes: '(min-width: 900px) 640px, 100vw', label: 'Step image pending', cls: 'step-img' })}</div>
  <div class="step-body">
    <p class="stepnum num">${String(i + 1).padStart(2, '0')}<span> / ${String(steps.length).padStart(2, '0')}</span></p>
    <h2 id="st-${esc(s.id)}">${esc(s.title)}</h2>
    ${s.group ? `<p class="eyebrow">${esc(s.group)}</p>` : ''}
    ${s.notes.length ? `<ol class="notes">${s.notes.map((n) => `<li>${esc(n)}</li>`).join('')}</ol>` : ''}
    ${s.parts.length ? `<div class="taggroup"><h3>Parts</h3><ul class="tags">${s.parts.map((p) => badge(p, 'part', root)).join('')}</ul></div>` : ''}
    ${s.tools.length ? `<div class="taggroup"><h3>Tools</h3><ul class="tags">${s.tools.map((p) => badge(p, 'tool', root)).join('')}</ul></div>` : ''}
    ${s.check || s.checkImage ? `<div class="checkbox"><h3><span class="tick" aria-hidden="true"></span>Check</h3>${s.check ? `<p>${esc(s.check)}</p>` : ''}${s.checkImage ? `<div class="checkimg">${themed(s.checkImage, root, { alt: s.checkImage.title, sizes: '320px' })}</div>` : ''}</div>` : ''}
    ${s.warnings.map((w) => `<p class="warnbox" role="note"><strong>Warning.</strong> ${esc(w)}</p>`).join('')}
  </div>
</article>`).join('');

  return `
<section class="pagehero compact" aria-labelledby="h1">
  <div class="wrap pagehero-copy">
    <p class="eyebrow">Build</p>
    <h1 id="h1">Assemble it,<br>one step at a time.</h1>
    <p class="lede">${steps.length ? `${steps.length} steps for the Rev A bench pod.` : 'Build steps.'} No soldering iron: the boards arrive assembled. Every step lists its parts and tools and ends with a check.</p>
  </div>
</section>

<div class="wrap">
  <div class="callout danger-note" role="note"><p><strong>Bench only.</strong> The finished device is never worn and never connected to a cannula in a person or animal. These steps end with a pod on a table delivering water into a container.</p></div>
  ${media.stepsInterim ? `<div class="callout" role="note"><p><strong>Illustrated guide in progress.</strong> Until <code>docs/build-guide/steps.json</code> and its images exist, these steps follow <code>mechanical/ASSEMBLY.md</code> and show component views instead of step drawings. No order has been placed yet, so no step has been followed end to end on real parts.</p></div>` : ''}
</div>

<section class="wrap guide" data-guide aria-label="Build steps">
  ${steps.length ? `<div class="guide-bar" hidden data-guide-bar>
    <div class="progress" role="progressbar" aria-label="Build progress" aria-valuemin="1" aria-valuemax="${steps.length}" aria-valuenow="1"><i></i></div>
    <ol class="dots">${steps.map((s, i) => `<li><button type="button" data-goto="${i}" aria-label="Step ${i + 1}: ${esc(s.title)}"><span class="num">${i + 1}</span></button></li>`).join('')}</ol>
  </div>` : ''}
  <div class="steps-wrap" aria-live="polite">${stepHtml}</div>
  ${steps.length ? `<div class="guide-nav" hidden data-guide-nav>
    <button type="button" class="btn" data-prev>Previous</button>
    <span class="guide-pos num" data-pos>Step 1 of ${steps.length}</span>
    <button type="button" class="btn primary" data-next>Next step</button>
  </div>` : '<p class="muted">No build steps found at build time.</p>'}
</section>

<section class="wrap block" aria-labelledby="pre-h">
  <h2 id="pre-h" class="h-sm">Before you start</h2>
  <div class="prestart">
    <div><h3>Order</h3><p>Parts, sources and prices are on <a href="${root}parts/">Parts and cost</a>, with the full ${link('docs/SHOPPING.md', 'shopping list')}. Buy a sample set first: every part marked “lock after sample” is measured before the CAD is frozen.</p></div>
    <div><h3>Print and test the dock</h3><p>The cannula head dimensions are not public. Print the fit-test coupon and try it on a real head first: ${link('mechanical/cannula-measurement.md', 'cannula measurement sheet')}.</p></div>
    <div><h3>Then test</h3><p>Flash the controller and run bench tests with water: ${link('firmware-rs/docs/bench-testing.md', 'firmware bench testing')}. The <a href="${root}safety/#bench-h">verification plan</a> lists the acceptance criteria.</p></div>
  </div>
  ${tools.length ? `<details class="tech"><summary>Tools you need (${tools.length})</summary><ul class="tags">${tools.map((t) => badge(t, 'tool', root)).join('')}</ul></details>` : ''}
  <details class="tech"><summary>All build documents (${guides.length})</summary>
    <ul class="linklist">${guides.map((e) => `<li><a href="${docUrl(e, root)}"><strong>${esc(e.title)}</strong></a><span class="num">${esc(e.path)}</span></li>`).join('')}</ul>
  </details>
</section>`;
}
