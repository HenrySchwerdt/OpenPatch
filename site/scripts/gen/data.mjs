// Parsers that turn the repo documents into structured data. Tolerant on purpose: when a source file
// is missing or its tables change shape, the corresponding page degrades to a visible "source missing" note
// instead of failing the build (the doc agents are still moving these files).
import { exists, plain, read, section, tables } from './lib.mjs';

const clean = (s) => plain(s).replace(/^`|`$/g, '');
const col = (headers, re) => headers.findIndex((h) => re.test(plain(h)));

// ---------------------------------------------------------------- fault catalogue (docs/06-diagnostics.md)
export const SEVERITY = {
  I: { label: 'Info', rank: 0, text: 'Logged only. No alert.' },
  W: { label: 'Warning', rank: 1, text: 'Delivery continues. The user should act soon.' },
  F: { label: 'Fault', rank: 2, text: 'Delivery stops. Cleared by acknowledge once the cause is gone.' },
  L: { label: 'Latched', rank: 3, text: 'Delivery stops and survives reboot and acknowledge. Only the verification test clears it.' },
};

export function parseFaults() {
  const src = read('docs/06-diagnostics.md');
  if (!src) return null;
  const all = tables(src);
  // layers from the counts table, FRUs, actions, components
  const layers = {};
  const cnt = all.find((t) => /^layer$/i.test(plain(t.headers[0])) && /codes/i.test(plain(t.headers[1] ?? '')));
  for (const r of cnt?.rows ?? []) {
    const m = /^([0-9A-F])\s+(\S+)\s*(?:\((.*)\))?/.exec(plain(r[0]));
    if (m) layers[m[1]] = { id: m[1], short: m[2], name: m[3] || m[2] };
  }
  const fruT = all.find((t) => /^id$/i.test(plain(t.headers[0])) && /^short$/i.test(plain(t.headers[1] ?? '')) && /FRU/i.test(t.headers[2] ?? ''));
  const frus = {};
  for (const r of fruT?.rows ?? []) frus[plain(r[1])] = { short: plain(r[1]), name: plain(r[2]), content: plain(r[3] ?? '') };
  const actT = all.find((t) => /^id$/i.test(plain(t.headers[0])) && /^name$/i.test(plain(t.headers[1] ?? '')) && /meaning/i.test(t.headers[2] ?? ''));
  const actions = {};
  for (const r of actT?.rows ?? []) actions[plain(r[1])] = plain(r[2]);
  const compT = all.find((t) => /^layer$/i.test(plain(t.headers[0])) && /^comp$/i.test(plain(t.headers[1] ?? '')));
  const comps = {};
  for (const r of compT?.rows ?? []) {
    for (const id of plain(r[1]).split(/[,\s]+/).filter(Boolean)) comps[`${plain(r[0])}-${id.toUpperCase()}`] = { name: plain(r[2]), refs: plain(r[3] ?? ''), fru: plain(r[4] ?? '') };
  }

  const codes = [];
  for (const t of all) {
    if (!/^code$/i.test(plain(t.headers[0])) || col(t.headers, /^sev/i) < 0) continue;
    const ix = {
      name: col(t.headers, /^name/i), det: col(t.headers, /detection/i), by: col(t.headers, /^by$/i), sev: col(t.headers, /^sev/i),
      fru: col(t.headers, /^fru/i), haz: col(t.headers, /^haz/i), test: col(t.headers, /^test/i), trio: col(t.headers, /trio/i),
    };
    for (const r of t.rows) {
      const code = clean(r[0]);
      const m = /^([0-9A-F])-([0-9A-F]{2})-([0-9A-F]{3})$/i.exec(code);
      if (!m) continue;
      const sev = clean(r[ix.sev]).slice(0, 1).toUpperCase();
      const fruCell = plain(r[ix.fru] ?? '');
      const fm = /^(.*?):\s*(.+)$/.exec(fruCell);
      const fruText = fm ? fm[1].trim() : fruCell;
      const action = fm ? fm[2].trim() : '';
      const primary = fruText.split(/[\s(]/)[0];
      const layer = m[1].toUpperCase();
      const comp = comps[`${layer}-${m[2].toUpperCase()}`];
      codes.push({
        code: code.toUpperCase(), layer, layerName: layers[layer]?.name ?? layer, layerShort: layers[layer]?.short ?? layer,
        comp: m[2].toUpperCase(), component: comp?.name ?? '', refs: comp?.refs ?? '',
        name: clean(r[ix.name]), detection: plain(r[ix.det] ?? ''), by: plain(r[ix.by] ?? ''),
        sev: SEVERITY[sev] ? sev : '?', fruText, fru: primary, fruName: frus[primary]?.name ?? '', action, actionText: actions[action] ?? '',
        hazards: plain(r[ix.haz] ?? ''), tests: plain(r[ix.test] ?? ''), trio: plain(r[ix.trio] ?? ''),
      });
    }
  }
  const counts = { I: 0, W: 0, F: 0, L: 0 };
  for (const c of codes) if (counts[c.sev] !== undefined) counts[c.sev]++;
  return { codes, layers: Object.values(layers), frus, actions, counts, total: codes.length };
}

// ---------------------------------------------------------------- status (docs/STATUS.md)
export function classify(text) {
  const t = plain(text);
  if (/not verified|no drc|untested|not tested|interrupted|not orderable|not built|63 errors|^no\b|stopped/i.test(t)) return 'unverified';
  if (/\b\d+\s*(host\s*)?tests?\b|\bpass|build ok|green|\blive\b|drc 0/i.test(t)) return 'verified';
  return 'partial';
}

export function parseStatus() {
  const src = read('docs/STATUS.md');
  if (!src) return null;
  const all = tables(src);
  const handoffMd = section(src, /^HANDOFF/);
  const handoffT = all.find((t) => /state/i.test(t.headers[1] ?? '') && /verified/i.test(t.headers[2] ?? ''));
  const perT = all.find((t) => /^status$/i.test(plain(t.headers[1] ?? '')) && /verified/i.test(t.headers[2] ?? ''));
  const rowsOf = (t) => (t?.rows ?? []).map((r) => ({ area: plain(r[0]).replace(/\*\*/g, ''), state: r[1] ?? '', verified: r[2] ?? '', next: r[3] ?? '', cls: classify(r[2] ?? '') }));
  const warnings = [...src.matchAll(/^>\s*(?:⚠️|WARNING)\s*(.*)$/gm)].map((m) => m[1].replace(/^\*\*(.*?)\*\*/, '$1').trim());
  const decisions = section(src, /^Decision log/).split('\n').filter((l) => /^-\s/.test(l)).map((l) => l.replace(/^-\s+/, ''));
  const nextSteps = handoffMd.split('\n').filter((l) => /^\d+\.\s/.test(l)).map((l) => l.replace(/^\d+\.\s+/, ''));
  const updated = /Last updated:\s*\*\*([^*]+)\*\*/.exec(src)?.[1] ?? '';
  const architecture = /\*\*Current architecture \(decided\):\*\*\s*([^\n]+)/.exec(handoffMd)?.[1] ?? '';
  return { handoff: rowsOf(handoffT), perArea: rowsOf(perT), warnings, decisions, nextSteps, updated, architecture };
}

// ---------------------------------------------------------------- parts lock (docs/PARTS-LOCK.md)
export function parseParts() {
  const src = read('docs/PARTS-LOCK.md');
  if (!src) return null;
  const t = tables(src).find((x) => /function/i.test(x.headers[1] ?? '') && /status/i.test(x.headers.join(' ')));
  if (!t) return null;
  const ix = { fn: col(t.headers, /function/i), part: col(t.headers, /chosen/i), backup: col(t.headers, /backup/i), src: col(t.headers, /source/i), price: col(t.headers, /price/i), status: col(t.headers, /status/i), why: col(t.headers, /why/i) };
  return t.rows.map((r) => {
    const status = plain(r[ix.status]).toUpperCase();
    return {
      no: plain(r[0]), fn: plain(r[ix.fn]), part: r[ix.part], partPlain: plain(r[ix.part]), backup: plain(r[ix.backup]), source: plain(r[ix.src]), price: plain(r[ix.price]),
      status, statusKey: /AFTER/.test(status) ? 'sample' : /CANDIDATE/.test(status) ? 'candidate' : 'locked', why: r[ix.why] ?? '',
    };
  });
}

// ---------------------------------------------------------------- spec tables
export function parseSpec() {
  const src = read('spec/design-parameters.md');
  if (!src) return null;
  const envT = tables(src).find((t) => /^size$/i.test(plain(t.headers[0])) && /DASH/i.test(t.headers.join(' ')));
  const envelope = (envT?.rows ?? []).map((r) => {
    const m = /(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)\s*[×x]\s*(\d+(?:\.\d+)?)/.exec(plain(r[2]));
    return { size: plain(r[0]), volume: plain(r[1]), l: m ? +m[1] : null, w: m ? +m[2] : null, h: m ? +m[3] : null, dash: plain(r[3] ?? '') };
  });
  const lim = section(src, /^7\.\s*Safety limits/).split('\n').filter((l) => /^-\s/.test(l));
  const limits = lim.map((l) => {
    const body = l.replace(/^-\s+/, '');
    const i = body.indexOf(':');
    return i < 0 ? { name: plain(body), value: '' } : { name: plain(body.slice(0, i)), value: body.slice(i + 1).trim() };
  });
  const stadium = { w: 16, h: 5 };
  const area = 5 * (stadium.w - stadium.h) + Math.PI * (stadium.h / 2) ** 2;
  return { envelope, limits, area, src };
}

export const hasFile = exists;
