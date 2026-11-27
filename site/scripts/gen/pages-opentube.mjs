// OpenTube product page (URL opentube/): the tubed pump around a 1.6 ml Insight-class cartridge with the original Accu-Chek Insight
// Adapter & Tubing as its front cap (repository name: cart pump A, v2). Same structure as the OpenPatch page: hero, key numbers,
// content sections, status, and the sibling model at the end. Numbers: facts-opentube.mjs; images: docs/renders/manifest.json
// entries with product "opentube".
import { blobUrl, esc, read, slug } from './lib.mjs';
import { barPair, formula, stage } from './pages-home.mjs';
import { familySwitch, models, sibling, testOnly } from './family.mjs';
import { OT_BRIEF, OT_REPORT } from './facts-opentube.mjs';

const f1 = (n) => (n == null ? 'n/a' : (Math.round(n * 10) / 10).toFixed(1));
const v = (n) => (n == null ? 'n/a' : esc(n));

/** Anchor of the "Cart A v2: mechanical order" section in docs/CART-ORDER.md (same slug rule as the doc renderer). */
function orderAnchor() {
  const h = /^##\s+(.*mechanical order.*)$/im.exec(read('docs/CART-ORDER.md') ?? '')?.[1];
  return h ? `#${slug(h)}` : '';
}

/** Plan-view schematic of the yoke drive at FULL (not to scale; positions follow the brief's numbers, x 7 px/mm, y 4 px/mm). */
function yokeSchematic(T) {
  const X = (mm) => 30 + mm * 7;
  const Y = (mm) => 44 + mm * 4;
  const ax = Y(11.46), sc = Y(25.6), mo = Y(33.4);
  const cx = (X(71.86) + X(81.36)) / 2;
  return `<figure class="schem">
<div class="schem-scroll" role="region" aria-label="Yoke drive schematic" tabindex="0">
<svg viewBox="0 0 640 262" class="drawing" role="img" aria-labelledby="yk-t yk-d">
<title id="yk-t">Yoke drive, plan view, schematic</title>
<desc id="yk-d">The glass cartridge lies along the near side and ends at the Insight adapter. Behind the cartridge a lead screw runs parallel to it, offset to the side, turned by the gearmotor through a small pinion and a larger gear. A yoke rides on the screw nut and carries a plain push stem along the cartridge axis; the stem passes the stop ring and presses the stopper forward by up to the full stroke.</desc>
<path class="sk-house" d="M${X(5)} ${Y(0)} H${X(71.86)} V${Y(49)} H${X(65.26)} C${X(58)} ${Y(49)} ${X(54)} ${Y(38)} ${X(48)} ${Y(38)} H${X(5)} A35 20 0 0 1 ${X(0)} ${Y(33)} V${Y(5)} A35 20 0 0 1 ${X(5)} ${Y(0)} Z"/>
<rect class="sk-adapter" x="${X(71.86)}" y="${Y(0)}" width="${X(81.36) - X(71.86)}" height="${Y(49) - Y(0)}" rx="10"/>
<line class="sk-tube" x1="${X(81.36)}" y1="${Y(40)}" x2="${X(81.36) + 22}" y2="${Y(40)}"/>
<rect class="sk-cart" x="${X(28.56)}" y="${ax - 22}" width="${X(71.56) - X(28.56)}" height="44" rx="8"/>
<rect class="sk-stopper" x="${X(28.9)}" y="${ax - 19}" width="${X(36.9) - X(28.9)}" height="38" rx="4"/>
<rect class="sk-ring" x="${X(27.56)}" y="${ax - 27}" width="7" height="54"/>
<line class="sk-stem" x1="${X(4.4)}" y1="${ax}" x2="${X(28.9)}" y2="${ax}"/>
<rect class="sk-yoke" x="${X(2)}" y="${ax - 6}" width="${X(4.4) - X(2)}" height="${sc - ax + 12}" rx="3"/>
<line class="sk-screw" x1="${X(0.6)}" y1="${sc}" x2="${X(32)}" y2="${sc}"/>
<rect class="sk-gear" x="${X(28.66)}" y="${sc - 24}" width="${X(32.66) - X(28.66)}" height="48" rx="2"/>
<rect class="sk-motor" x="${X(9)}" y="${mo - 12}" width="${X(27.86) - X(9)}" height="24" rx="6"/>
<rect class="sk-gear" x="${X(28.66)}" y="${mo - 7}" width="${X(32.66) - X(28.66)}" height="14" rx="2"/>
<path class="sk-arrow" d="M${X(3.2)} 28 H${X(3.2 + (T.stroke ?? 0))}"/><path class="sk-head" d="M${X(3.2 + (T.stroke ?? 0))} 28 l-9 -5 v10 z"/>
<text x="${X(3.2)}" y="18" class="szd">stroke ${f1(T.stroke)} mm</text>
<text x="${X(44)}" y="${ax + 5}">cartridge</text>
<text x="${X(26.6)}" y="${ax - 32}" class="szd">stop ring</text>
<text x="${X(9)}" y="${ax - 8}" class="szd">push stem</text>
<text x="${X(5.4)}" y="${(ax + sc) / 2 + 4}" class="szd">yoke</text>
<text x="${X(34)}" y="${sc + 4}" class="szd">gear z${v(T.drive?.gear)} on the ${v(T.drive?.screw)} screw</text>
<text x="${X(9)}" y="${mo + 30}" class="szd">gearmotor, pinion z${v(T.drive?.pinion)}</text>
<text x="${cx}" y="${Y(24.5) + 4}" class="szc" text-anchor="middle" transform="rotate(-90 ${cx} ${Y(24.5)})">INSIGHT ADAPTER</text>
</svg></div>
<figcaption>Schematic plan view with a full cartridge, not to scale, drawn from the part positions in the design brief (sections 6 to 10). The stem passes through the stop ring into the cartridge.</figcaption>
</figure>`;
}

export function opentube(ctx) {
  const { root, facts: F, media, ot: T, d } = ctx;
  const M = media.product('opentube');
  const rear = M.byId('opentube_hero_rear');
  const front = M.byId('opentube_hero_front');
  const usb = M.byId('opentube_usb');
  const xray = M.byId('opentube_xray');
  const top = M.byId('opentube_top');
  const brief = d(OT_BRIEF);
  const S = T.size;
  const I = T.insight;
  const gates = T.interlock ? T.interlock.split(/\s+AND\s+/).length : null;

  const tiles = [];
  if (S && I) tiles.push(`<li class="fact"><p class="big">${f1(S.l)}<span class="u">mm</span></p><h3>Long, adapter included</h3><p>${f1(S.l)} × ${S.w} × ${S.h} mm with the adapter on. The Accu-Chek Insight measures ${I.l} × ${I.w} × ${I.h} mm${T.insightRef ? ` (${esc(T.insightRef)})` : ''}.</p>${barPair({ label: 'OpenTube', v: S.l }, { label: 'Insight', v: I.l })}</li>`);
  if (T.envelope != null && I?.box) tiles.push(`<li class="fact"><p class="big">${f1(T.envelope)}<span class="u">ml</span></p><h3>Envelope</h3><p>${T.vsInsight ? `${esc(T.vsInsight)} against` : 'Against'} the ${I.box} ml box of the Insight. Only the head needs the full ${S?.w ?? 'n/a'} × ${S?.h ?? 'n/a'} mm face; the body behind it is narrower.</p>${barPair({ label: 'OpenTube', v: T.envelope }, { label: 'Insight', v: I.box }, 'millilitres')}</li>`);
  if (T.cart) tiles.push(`<li class="fact"><p class="big">${f1(T.cart.ml)}<span class="u">ml</span></p><h3>Standard glass cartridge</h3><p>Insight class, ${esc(T.cart.iso ?? '')}, ${v(T.cart.od)} mm across and ${v(T.cart.len)} mm long. A ${f1(T.stroke)} mm stroke moves ${v(T.deliverable)} ml. Bought empty, filled with water for bench tests.</p></li>`);
  if (T.interlock) tiles.push(`<li class="fact"><p class="big">${gates}<span class="u">conditions</span></p><h3>Same interlock as OpenPatch</h3><p>Same electronics. The motor gets power only when all ${gates} hold:</p><p class="chiprow">${formula(T.interlock)}</p></li>`);

  const steps = [
    ['Adapter off', 'The lock is open, so the drive may only run in reverse: the push stem goes back home.', 'Lock open · reverse only', 'rev'],
    ['Cartridge in', 'The cartridge slides in through the head until its rear end sits on the stop ring. Its cap face then lies just below the head face, where the adapter seals.', 'Lock open · reverse only', 'rev'],
    ['Adapter on, 90° turn', 'The original Insight adapter goes on with a 90 degree clockwise turn. Its needle enters the cartridge septum; the tubing leaves at the far end.', 'Lock open · reverse only', 'rev'],
    ['Lock switch closes', 'Locked, the adapter presses a 2 mm steel ball in the head, the ball pushes a pin onto a detector switch. Closed means locked; a broken wire reads as unlocked.', 'Lock closed', 'fwd'],
    ['Only then forward', 'Now the interlock allows forward motion. The firmware advances the stem to the stopper and primes, into a container on the bench. Water only.', 'Lock closed · forward allowed', 'fwd'],
  ];

  const form = [
    ['USB-C on the seam', 'Charge and data through a stadium-shaped opening centred on the seam, half in each shell, with no thin bridge.'],
    ['Button and LED on top', 'A button plunger and an LED light pipe sit on the flat top, above the board.'],
    ['Two printed halves', 'The housing splits at the cartridge axis. Both halves print without supports on visible faces.'],
    ['No visible screws', 'Two axial M2 screws hold the head, hidden under the adapter; the rear closes with hooks. No text or logo on the case.'],
    ['Nothing fragile', 'No free-standing pins or fins; every part is held by geometry once the case is closed.'],
    ['No soldering iron', 'Cell and motor are meant to plug into connectors on the board (spec section 1a). The connector layout is still open.'],
  ];

  const status = [
    ['Done on screen', [
      `Design brief and package study: every part placed${T.check ? `, ${T.check.pass ? 'no collisions and every part inside the cavity at full and empty' : 'package check currently failing'}` : ''}.`,
      T.printPartCount ? `Print parts generated: ${T.printPartCount} parts${T.shellsOk ? ', each one valid solid' : ''}.` : 'Print parts generated.',
      'Renders of the v2 form.',
    ]],
    ['In progress', ['v2 print parts in fit testing (all parts on one print bed).', 'Main board being routed.']],
    ['Open', ['Antenna wing and plug-in connectors on the board.', 'Any bench test with water: nothing is verified on the bench yet.', 'The mylife YpsoPump adapter.']],
  ];

  return `
<section class="pagehero" aria-labelledby="h1">
  <div class="wrap pagehero-copy">
    ${familySwitch(root, 'opentube')}
    <p class="eyebrow">OpenTube · tubed pump · in development</p>
    <h1 id="h1">Built around<br>the cartridge.</h1>
    <p class="lede">OpenTube holds a ${T.cart ? `${f1(T.cart.ml)} ml ` : ''}Insight-class glass cartridge and takes the original Accu-Chek Insight Adapter &amp; Tubing as its front cap.${S ? ` ${f1(S.l)} × ${S.w} × ${S.h} mm with the adapter on.` : ''} Same electronics and hardware interlock as OpenPatch.</p>
    ${testOnly(root)}
  </div>
  <div class="wrap hero-stage">${stage(rear, root, { sizes: '(min-width: 1240px) 1160px, 100vw', eager: true, cls: 'hero-img ot' })}</div>
</section>

<section class="wrap facts" aria-label="OpenTube key numbers">
  ${tiles.length ? `<ul class="factgrid">${tiles.join('')}</ul>` : '<p class="callout warn">The OpenTube package report was not found at build time.</p>'}
  <p class="factnote">Sizes and volumes from <a href="${blobUrl(OT_REPORT)}">${OT_REPORT}</a> (written by <span class="num">mechanical/cart_a_v2/package.py</span>). Cartridge, stroke, drive and interlock from the <a href="${brief}">OpenTube design brief</a>, sections 1, 3 and 7. Insight size from its user manual, appendix A, as quoted in the brief.</p>
</section>

<section class="wrap block" aria-labelledby="form-h">
  <div class="split2 ot-form">
    <div>
      <p class="eyebrow">Form</p>
      <h2 id="form-h">One clean shape, no visible screws.</h2>
      <ul class="limitgrid two">${form.map(([t, p]) => `<li><h3>${esc(t)}</h3><p>${esc(p)}</p></li>`).join('')}</ul>
    </div>
    <div class="shots">
      <figure class="shot">${stage(front, root, { sizes: '(min-width: 56rem) 600px, 100vw' })}<figcaption>${esc(front?.caption ?? '')}</figcaption></figure>
      <figure class="shot">${stage(usb, root, { sizes: '(min-width: 56rem) 600px, 100vw' })}<figcaption>${esc(usb?.caption ?? '')}</figcaption></figure>
    </div>
  </div>
</section>

<section class="wrap block" aria-labelledby="in-h">
  <div class="split2 img-first">
    <div>
      <p class="eyebrow">Inside</p>
      <h2 id="in-h">The cartridge gets a room of its own.</h2>
      <p class="lede sm">The cartridge chamber is a closed tube from the head back to a rear bulkhead. Motor and electronics sit in their own bays, so dirt, or water from a leak, stays on the cartridge side.</p>
      <dl class="bays">
        <div><dt>Cartridge chamber</dt><dd>Closed off from motor and electronics. The barrel rests on a rear stop ring; only the push stem passes through it.</dd></div>
        <div><dt>Drive bay</dt><dd>${T.drive ? `${esc(T.drive.motor)} gearmotor beside the screw, z${T.drive.pinion} : z${T.drive.gear} gears, ${esc(T.drive.screw)} screw, a printed yoke and a steel push stem.` : 'Gearmotor, gears, screw, yoke and push stem.'}</dd></div>
        <div><dt>Electronics bay</dt><dd>Main board centred on the seam, the cell above it, button and LED on top, sounder slots in the floor.</dd></div>
      </dl>
    </div>
    <figure class="shot">${stage(xray, root, { sizes: '(min-width: 56rem) 640px, 100vw' })}<figcaption>${esc(xray?.caption ?? '')}</figcaption></figure>
  </div>
</section>

<section class="story ot-how" aria-labelledby="how-h">
  <div class="wrap">
    <p class="eyebrow">How it works</p>
    <h2 id="how-h">Forward only after the adapter locks.</h2>
    <ol class="flowsteps">${steps.map(([t, p, st, k], i) => `<li><p class="fs-n num">${String(i + 1).padStart(2, '0')}</p><h3>${esc(t)}</h3><p>${esc(p)}</p><p class="fs-state fs-${k}">${esc(st)}</p></li>`).join('')}</ol>
    <div class="yoke">
      <div>
        <h3 class="h-sm">Why it is short: the yoke drive</h3>
        <p>The lead screw does not sit behind the cartridge, it runs beside the cartridge line. A printed yoke rides on the screw nut and pushes a plain steel stem into the cartridge.${T.yokeSaves ? ` That keeps the pump ${f1(T.yokeSaves)} mm shorter than a screw in line.` : ''}</p>
        <p>The ${v(T.drive?.screw)} screw is self-locking: pressure in the cartridge cannot push the stopper back, and the stem only moves under power, behind the interlock.${T.thrust ? ` Thrust ${T.thrust.have} N against ${T.thrust.need} N needed.` : ''}</p>
        <p class="note">Steps and drive from the <a href="${brief}">design brief</a>, sections 1, 4 and 7.</p>
      </div>
      ${yokeSchematic(T)}
    </div>
  </div>
</section>

<section class="wrap block" aria-labelledby="size-h">
  <div class="split2">
    <div>
      <p class="eyebrow">Size</p>
      <h2 id="size-h">Shorter than an Insight, a quarter less volume.</h2>
      <p class="lede sm">The adapter sits flush on the head, so the front face is ${S ? `${S.w} × ${S.h}` : 'n/a'} mm. Length follows from the cartridge, the ${f1(T.stroke)} mm stroke and the drive; the body behind the head is narrower.</p>
      <div class="tablewrap" role="region" aria-label="OpenTube and Accu-Chek Insight size" tabindex="0"><table>
        <caption>OpenTube from the package report, Insight from its ${esc(T.insightRef ?? 'user manual')} as quoted in the brief.</caption>
        <thead><tr><th scope="col">Pump</th><th scope="col">L × W × H, mm</th><th scope="col">Volume, ml</th></tr></thead>
        <tbody>
          <tr><th scope="row">OpenTube, with adapter</th><td class="num">${S ? `${f1(S.l)} × ${S.w} × ${S.h}` : 'n/a'}</td><td class="num">${f1(T.envelope)} envelope</td></tr>
          <tr><th scope="row">Accu-Chek Insight</th><td class="num">${I ? `${I.l} × ${I.w} × ${I.h}` : 'n/a'}</td><td class="num">${I?.box ?? 'n/a'} box</td></tr>
        </tbody></table></div>
    </div>
    <figure class="shot">${stage(top, root, { sizes: '(min-width: 56rem) 640px, 100vw' })}<figcaption>${esc(top?.caption ?? '')}</figcaption></figure>
  </div>
</section>

<section class="wrap block" aria-labelledby="ad-h">
  <p class="eyebrow">Adapters</p>
  <h2 id="ad-h">One cartridge class, more than one adapter.</h2>
  <ul class="adapters">
    <li class="adapter">
      <p><span class="badge st-sample">In development</span></p>
      <h3>Accu-Chek Insight Adapter &amp; Tubing</h3>
      <p>The original adapter is the front cap: a bayonet with a 90° turn, its needle into the cartridge septum, the tubing out of the far end. v2 print parts are in fit testing; the main board is being routed.</p>
      <dl class="specs"><div><dt>Cartridge</dt><dd><span class="num">${T.cart ? f1(T.cart.ml) : 'n/a'}</span> <span class="u">ml class</span></dd></div><div><dt>Front face</dt><dd><span class="num">${S ? `${S.w} × ${S.h}` : 'n/a'}</span> <span class="u">mm</span></dd></div><div><dt>Lock detection</dt><dd>ball, pin, switch</dd></div></dl>
    </li>
    <li class="adapter planned">
      <p><span class="badge st-planned">Planned</span></p>
      <h3>mylife YpsoPump adapter</h3>
      <p>A second OpenTube variant for the YpsoPump adapter, with the same ${T.cart ? `${f1(T.cart.ml)} ml ` : ''}cartridge class. Nothing is designed yet.</p>
    </li>
  </ul>
  <p class="note">Accu-Chek and Insight (Roche) and mylife YpsoPump (Ypsomed) are named only to describe the mechanical interface. No affiliation or endorsement. The adapters are used on the bench with water only, never on a person.</p>
</section>

<section class="wrap block" aria-labelledby="st-h">
  <p class="eyebrow">Status</p>
  <h2 id="st-h">Drawn and checked on screen. Not yet on the bench.</h2>
  <div class="statuscols">${status.map(([h, items]) => `<div><h3>${esc(h)}</h3><ul>${items.map((x) => `<li>${esc(x)}</li>`).join('')}</ul></div>`).join('')}</div>
  <p class="note">In the repository OpenTube is called <strong>cart pump A</strong>: brief <span class="num">${OT_BRIEF}</span>, CAD <span class="num">mechanical/cart_a_v2/</span>, print files <span class="num">mechanical/print/cart_A/</span>, generated data <span class="num">mechanical/out/cart_a_v2/</span>.</p>
  <ul class="linklist">
    <li><a class="arrow" href="${brief}">Design brief</a><span>Every part and requirement, the package study, the review and the print parts.</span></li>
    <li><a class="arrow" href="${d('docs/CART-ORDER.md')}${orderAnchor()}">Mechanical order list</a><span>Bought parts for the v2 fit test, with prices.</span></li>
    <li><a class="arrow" href="${root}status/">Project status</a><span>What is verified and what is not, for the whole project.</span></li>
  </ul>
</section>

${sibling(models(media, F, T), 'opentube', root)}`;
}
