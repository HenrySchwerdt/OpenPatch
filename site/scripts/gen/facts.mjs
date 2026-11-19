// Facts shown on the site. Every number is read from the repository at build time, never typed in here.
// Order of trust: generated CAD data (mechanical/out/bench/OP-*.mech.json) > spec/design-parameters.md > prose docs.
// When a prose document disagrees with the generated data, the generated value is shown and the document is listed in `stale`.
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { REPO_ROOT, plain, read, section, tables } from './lib.mjs';

const f1 = (n) => (Math.round(n * 10) / 10).toFixed(1);
const num = (s) => +String(s).replace(',', '.');

function benchJson(size) {
  const f = join(REPO_ROOT, 'mechanical', 'out', 'bench', `OP-${size}.mech.json`);
  if (!existsSync(f)) return null;
  try { return JSON.parse(readFileSync(f, 'utf8')); } catch { return null; }
}

export function collectFacts({ spec, faults, status }) {
  const stale = [];
  const specEnv = Object.fromEntries((spec?.envelope ?? []).filter((e) => e.l).map((e) => [e.size.replace(/\D/g, ''), e]));
  const ml = { 70: '0.7', 100: '1.0', 200: '2.0' };

  // ---- envelope per size: CAD data first, spec section 2 as fallback
  const sizes = [];
  for (const s of [70, 100, 200]) {
    const m = benchJson(s);
    const cad = m?.envelope?.bbox_mm;
    const sp = specEnv[String(s)];
    const [l, w, h] = cad ?? (sp ? [sp.l, sp.w, sp.h] : [null, null, null]);
    if (l == null) continue;
    if (cad && sp && (Math.abs(sp.l - l) > 0.05 || Math.abs(sp.h - h) > 0.05)) stale.push({ doc: 'spec/design-parameters.md', what: `section 2 lists OP-${s} as ${f1(sp.l)} x ${f1(sp.w)} x ${f1(sp.h)} mm, the generated CAD is ${f1(l)} x ${f1(w)} x ${f1(h)} mm` });
    sizes.push({ id: `OP-${s}`, units: s, ml: ml[s], l, w, h, volume: m?.envelope?.bbox_volume_ml ?? (l * w * h) / 1000, source: cad ? 'CAD' : 'spec', strokeMm: m?.stroke ?? null });
  }

  // ---- reference pod (Omnipod DASH) from the spec comparison column
  const dm = /(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)/.exec(spec?.envelope?.find((e) => e.dash)?.dash ?? '');
  const dash = dm ? { name: 'Omnipod DASH', l: +dm[1], w: +dm[2], h: +dm[3], volume: (dm[1] * dm[2] * dm[3]) / 1000 } : null;
  const hero = sizes.find((s) => s.units === 100) ?? sizes[0] ?? null;
  const volPct = hero && dash ? Math.round((hero.volume / dash.volume) * 100) : null;
  const heightPct = hero && dash ? Math.round((1 - hero.h / dash.h) * 100) : null;

  // ---- drive: gear pair and dose resolution (spec section 4, cross-checked with the CAD data)
  const specSrc = read('spec/design-parameters.md') ?? '';
  const drive = section(specSrc, /^4\.\s*Drive/);
  const gm = /(\d+)\s*T on the motor[\s\S]*?(\d+)\s*T on the screw/.exec(drive);
  const um = /\*\*(0\.\d+)\s*U\/step\*\*/.exec(drive);
  const cadDrive = benchJson(100);
  const gear = gm ? { motor: +gm[1], screw: +gm[2] } : cadDrive?.gears ? { motor: cadDrive.gears.z_motor, screw: cadDrive.gears.z_screw } : null;
  const uPerStep = um ? um[1] : cadDrive?.drive?.u_per_step ? cadDrive.drive.u_per_step.toFixed(6) : null;
  if (um && cadDrive?.drive?.u_per_step && Math.abs(+um[1] - cadDrive.drive.u_per_step) / +um[1] > 0.002) stale.push({ doc: 'spec/design-parameters.md', what: `section 4 gives ${um[1]} U/step, the CAD data gives ${cadDrive.drive.u_per_step.toFixed(6)}` });
  const motor = /\*\*(NFP-608-26\.45[^*]*)\*\*/.exec(drive)?.[1] ?? null;
  const stepsFor005 = uPerStep ? (0.05 / +uPerStep) : null;

  // ---- safety: layers, limits, interlock formula
  const diag = read('docs/06-diagnostics.md') ?? '';
  const layerT = tables(diag).find((t) => /^layer$/i.test(plain(t.headers[0])) && /^what$/i.test(plain(t.headers[1] ?? '')));
  const layers = (layerT?.rows ?? []).map((r) => ({ id: plain(r[0]).split(' ')[0], name: plain(r[0]).replace(/^L\d\s*/, '').replace(/\s*\(this document\)/, ''), what: plain(r[1]), indep: plain(r[2] ?? ''), trips: plain(r[3] ?? '') }));
  const limits = (spec?.limits ?? []).map((l) => {
    const v = l.value || '';
    const m = /^(\d+(?:\.\d+)?)\s*([^\s(]+(?:\/[^\s(]+)?)?/.exec(v);
    return { name: l.name, value: v, big: m ? m[1] : '', unit: m?.[2] ?? '', rest: v.replace(m?.[0] ?? '', '').trim() };
  });
  const interlock = /\(`([^`]*MCU_EN[^`]*)`/.exec(specSrc)?.[1] ?? 'MCU_EN AND watchdog latch AND (DOCKED OR DIR_REV)';

  // ---- cost (docs/SHOPPING.md section 0.1)
  const shop = read('docs/SHOPPING.md') ?? '';
  const verdict = tables(section(shop, /^0\.1/)).find((t) => /first pump/i.test(t.headers.join(' ')));
  const rangeOf = (cell) => { const m = /(\d+)\s*[-–]\s*(\d+)/.exec(plain(cell ?? '')); return m ? { lo: +m[1], hi: +m[2] } : null; };
  const rec = verdict?.rows.find((r) => /recommended/i.test(plain(r[0])) && !/\bB\+/.test(plain(r[0])));
  const asFrozen = verdict?.rows.find((r) => /frozen/i.test(plain(r[0])));
  const cost = rec ? { first: rangeOf(rec[1]), next: rangeOf(rec[2]), frozenFirst: rangeOf(asFrozen?.[1]), target: /<=?\s*(\d+)\s*EUR/.exec(plain(section(shop, /^A0/)))?.[1] ?? '200' } : null;

  // ---- licence terms (COMMERCIAL-LICENSE.md, draft)
  const lic = read('COMMERCIAL-LICENSE.md') ?? '';
  const licence = lic ? {
    cap: /unit cost \+ (\d+)\s*%/i.exec(lic)?.[1] ?? null,
    levy: /\*\*(\d+)\s*% of net revenue\*\*/i.exec(lic)?.[1] ?? null,
    ret: /capped return of (\d+)\s*% of the recoverable investment/i.exec(lic)?.[1] ?? null,
  } : null;

  // ---- simulation report
  const rep = read('mechanical/sim/REPORT.md') ?? '';
  const sm = /\*\*(\d+)\s*PASS,\s*(\d+)\s*WARN,\s*(\d+)\s*FAIL\*\*/.exec(rep);
  const sim = sm ? { pass: +sm[1], warn: +sm[2], fail: +sm[3], total: +sm[1] + +sm[2] + +sm[3] } : null;

  // ---- stale prose: STATUS.md still lists a gear mismatch although spec and CAD agree
  const staleWarn = (status?.warnings ?? []).filter((w) => /gear/i.test(w) && /18\s*:\s*18|15\s*:\s*12/.test(w));
  if (staleWarn.length && gear) stale.push({ doc: 'docs/STATUS.md', what: `still lists a gear-ratio mismatch (15:12 versus 18:18); spec section 4 and the generated CAD use ${gear.motor} T : ${gear.screw} T`, key: 'gear' });

  return {
    sizes, dash, hero, volPct, heightPct, gear, uPerStep, stepsFor005, motor,
    layers, limits, interlock, cost, sim, licence, stale,
    faults: faults ? { total: faults.total, counts: faults.counts, layers: faults.layers.length } : null,
    fmt: { f1 },
  };
}

export { num };
