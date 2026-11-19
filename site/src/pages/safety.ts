// Interlock simulator and hazard explorer.
export {};
const sim = document.querySelector<HTMLElement>('[data-sim]');
if (sim) {
  const ins = [...sim.querySelectorAll<HTMLInputElement>('input[data-in]')];
  const svg = sim.querySelector<SVGSVGElement>('.gate');
  const result = sim.querySelector<HTMLElement>('[data-sim-result]');
  const why = result?.querySelector<HTMLElement>('[data-sim-why]');
  const outText = svg?.querySelector<SVGTextElement>('[data-out-text]');
  const rows = [...document.querySelectorAll<HTMLElement>('.truth tbody tr')];
  const net = (n: string, on: boolean): void => { svg?.querySelector(`[data-net="${n}"]`)?.classList.toggle('on', on); };
  const update = (): void => {
    const v: Record<string, boolean> = {};
    for (const i of ins) v[i.dataset.in ?? ''] = i.checked;
    const or = v.docked || v.rev;
    const out = v.latch && v.mcu && or;
    net('docked', v.docked); net('rev', v.rev); net('or', or); net('mcu', v.mcu); net('latch', v.latch); net('out', out);
    svg?.classList.toggle('out-on', out);
    if (outText) outText.textContent = out ? 'ON (supplied)' : 'OFF';
    const idx = (v.docked ? 1 : 0) | (v.rev ? 2 : 0) | (v.mcu ? 4 : 0) | (v.latch ? 8 : 0);
    rows.forEach((r, i) => r.classList.toggle('cur', i === idx));
    result?.classList.toggle('on', out);
    if (result?.firstElementChild) result.firstElementChild.textContent = out ? 'Motor supply: ON.' : 'Motor supply: OFF.';
    if (why) why.textContent = rows[idx]?.lastElementChild?.textContent ?? '';
  };
  ins.forEach((i) => i.addEventListener('change', update));
  update();
}

const haz = document.querySelector<HTMLElement>('[data-hazards]');
if (haz) {
  const btns = [...haz.querySelectorAll<HTMLButtonElement>('[data-haz]')];
  const cards = [...haz.querySelectorAll<HTMLElement>('[data-haz-card]')];
  const show = (id: string): void => {
    btns.forEach((b) => b.setAttribute('aria-pressed', String(b.dataset.haz === id)));
    cards.forEach((c) => { c.hidden = c.dataset.hazCard !== id; });
  };
  btns.forEach((b) => b.addEventListener('click', () => show(b.dataset.haz ?? '')));
}
