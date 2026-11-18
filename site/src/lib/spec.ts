import { DASH, SIZES, fmt, type SizeId } from './sizes';
import { onSize } from './state';

const row = (label: string, value: string, unit = '', hl = false): string =>
  `<tr${hl ? ' class="hl"' : ''}><th scope="row">${label}</th><td>${value}${unit ? `<small>${unit}</small>` : ''}</td></tr>`;

function renderSpec(id: SizeId): void {
  const s = SIZES[id];
  const body = document.getElementById('spec-body');
  if (!body) return;
  const footprint = Math.round(((s.length * s.width) / (DASH.length * DASH.width)) * 100);
  const envelope = (s.length * s.width * s.height) / 1000;
  const dashEnvelope = (DASH.length * DASH.width * DASH.height) / 1000;
  body.innerHTML = [
    row('Reservoir', fmt(s.units), 'IE (U100)', true),
    row('Volumen', fmt(s.ml), 'ml'),
    row('L × B × H', `${s.length} × ${s.width} × ${fmt(s.height)}`, 'mm'),
    row('Kolbenhub', fmt(s.stroke), 'mm'),
    row('Gewicht (leer, Schätzung)', `≈ ${s.weightG}`, 'g'),
    row('Grundfläche vs. DASH', `${footprint}`, '%'),
    row('Hüllvolumen vs. DASH', `${Math.round((envelope / dashEnvelope) * 100)}`, `% · ${fmt(Math.round(envelope * 10) / 10)} ml`),
    row('Auflösung', '0,0131', 'IE / Schritt'),
  ].join('');
}

function renderScale(id: SizeId): void {
  const s = SIZES[id];
  const view = document.getElementById('scale-view');
  if (!view) return;
  view.dataset.size = id;
  view.querySelector('[data-op-name]')!.textContent = id;
  view.querySelector('[data-op-foot]')!.textContent = `${s.length} × ${s.width} mm`;
  view.setAttribute(
    'aria-label',
    `Maßstabsgetreuer Vergleich: Omnipod DASH 52 × 39 × 14,5 mm, ${id} ${s.length} × ${s.width} × ${fmt(s.height)} mm, 2-Euro-Münze`,
  );
}

export function initSpec(): void {
  onSize((id) => {
    renderSpec(id);
    renderScale(id);
  });
}
