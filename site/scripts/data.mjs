// Build-Zeit-Daten: BOM (electronics/bom.csv), Kosten (electronics/cost-pcbway.md), Modelle.
import { existsSync, readFileSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { marked } from 'marked';

const root = join(dirname(fileURLToPath(import.meta.url)), '..', '..');

export const esc = (s) =>
  String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c]);

function parseCsv(text) {
  const rows = [];
  let row = [];
  let cell = '';
  let q = false;
  const t = text.replace(/^﻿/, '');
  for (let i = 0; i < t.length; i++) {
    const c = t[i];
    if (q) {
      if (c === '"' && t[i + 1] === '"') { cell += '"'; i++; }
      else if (c === '"') q = false;
      else cell += c;
    } else if (c === '"') q = true;
    else if (c === ',') { row.push(cell); cell = ''; }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && t[i + 1] === '\n') i++;
      row.push(cell); cell = '';
      if (row.some((x) => x.trim() !== '')) rows.push(row);
      row = [];
    } else cell += c;
  }
  row.push(cell);
  if (row.some((x) => x.trim() !== '')) rows.push(row);
  return rows;
}

const FALLBACK_BOM = [
  ['Funktion', 'Bauteil (Konzept)', 'Anmerkung'],
  ['MCU / BLE', 'Nordic nRF54L15 (QFN48 6×6)', 'Fallback: nRF52833'],
  ['Motortreiber', 'ST STSPIN220', 'Alternative: TI DRV8834'],
  ['Sicherheits-Watchdog', 'TI TPL5010', 'schaltet Motorversorgung hart ab'],
  ['Motor', 'Ø 6 mm Schrittmotor (Faulhaber-ADM0620-Klasse)', '20 Schritte/U, 10:1 Getriebe'],
  ['Encoder', 'Hall-Sensor TMAG5273 / AS5600L-Klasse', 'unabhängige Fördermessung'],
  ['Qi-Empfänger', 'TI BQ51003', 'Spule Ø 20 mm'],
  ['Laderegler', 'TI BQ25120A', ''],
  ['Akku', 'Li-Po 302030 / 302530, 60–90 mAh', '3,0–3,5 mm dick, mit PCM'],
  ['Summer', 'Piezo 9 × 9 × 2 mm', 'eigener Ansteuerpfad'],
];

const BOM_COLS = [
  ['ref', 'Ref'],
  ['value', 'Wert'],
  ['description', 'Beschreibung'],
  ['manufacturer', 'Hersteller'],
  ['mpn', 'MPN'],
  ['package', 'Gehäuse'],
  ['qty', 'Stk'],
  ['line_eur_per_board', '€ / Board'],
];

export function bomHtml() {
  const file = join(root, 'electronics', 'bom.csv');
  const real = existsSync(file);
  let rows = real ? parseCsv(readFileSync(file, 'utf8')) : FALLBACK_BOM;
  if (real) {
    const head = rows[0].map((h) => h.trim().toLowerCase());
    const idx = BOM_COLS.map(([key]) => head.findIndex((h) => h === key || h.startsWith(key)));
    if (idx.every((i) => i >= 0)) {
      rows = [BOM_COLS.map(([, label]) => label), ...rows.slice(1).map((r) => idx.map((i) => r[i] ?? ''))];
    }
  }
  const [head, ...body] = rows;
  const cols = head.length;
  const thead = `<tr>${head.map((h) => `<th scope="col">${esc(h.trim())}</th>`).join('')}</tr>`;
  const tbody = body
    .map((r) => `<tr>${Array.from({ length: cols }, (_, i) => `<td>${esc((r[i] ?? '').trim())}</td>`).join('')}</tr>`)
    .join('');
  const note = real
    ? `<p class="table-note mono">${body.length} Positionen · generiert aus <code>electronics/bom.csv</code> (Preise: Schätzung bzw. Websuche, siehe Quelldatei)</p>`
    : `<p class="table-note mono">Konzept-Stückliste aus spec/design-parameters.md · die vollständige BOM erscheint hier, sobald <code>electronics/bom.csv</code> existiert.</p>`;
  return `<div class="table-wrap bom-wrap" tabindex="0" role="region" aria-label="Stückliste (scrollbar)"><table class="data-table bom"><thead>${thead}</thead><tbody>${tbody}</tbody></table></div>${note}`;
}

export function costHtml() {
  const file = join(root, 'electronics', 'cost-pcbway.md');
  if (!existsSync(file)) {
    return `<div class="cost-fallback"><p>Die Kostenaufstellung wird beim Build aus <code>electronics/cost-pcbway.md</code> übernommen. Sie liegt noch nicht vor.</p><p class="mono">Kostentreiber: PCBA (4-Lagen, 0,6 mm, Fine-Pitch-QFN) · Motor + Getriebe · Akku · Gehäuse (MJF/SLA) · Kanüle (gekauft)</p></div>`;
  }
  let md = readFileSync(file, 'utf8').replace(/^#\s+.*\n/, '');
  md = md.replace(/^(#{1,5})\s/gm, (m, h) => '#'.repeat(Math.min(h.length + 2, 6)) + ' ');
  const html = marked.parse(md, { async: false, gfm: true });
  const wrapped = html.replace(/<table>/g, '<div class="table-wrap" tabindex="0" role="region" aria-label="Kostentabelle (scrollbar)"><table class="data-table">').replace(/<\/table>/g, '</table></div>');
  return `<div class="prose">${wrapped}</div>`;
}

export function downloadsFromManifest() {
  const file = join(root, 'site', 'public', 'models', 'manifest.json');
  if (!existsSync(file)) return { models: [], others: [] };
  try {
    return JSON.parse(readFileSync(file, 'utf8'));
  } catch {
    return { models: [], others: [] };
  }
}

export function hasFile(rel) {
  return existsSync(join(root, rel));
}
