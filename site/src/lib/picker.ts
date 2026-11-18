interface SizeSpec { readonly length: number; readonly capacity: string; readonly volume: string }

const SIZES: Readonly<Record<string, SizeSpec>> = {
  '70': { length: 38, capacity: '0.7 mL · 70 U', volume: '10.3 mL' },
  '100': { length: 42, capacity: '1.0 mL · 100 U', volume: '11.4 mL' },
  '200': { length: 55.4, capacity: '2.0 mL · 200 U', volume: '15.1 mL' },
};

export function initPicker(): void {
  const root = document.querySelector<HTMLElement>('[data-picker]');
  if (!root) return;
  const buttons = [...root.querySelectorAll<HTMLButtonElement>('[data-size]')];
  const pics = [...root.querySelectorAll<HTMLElement>('[data-pic]')];
  const frame = root.querySelector<HTMLElement>('.picker-frame');
  const set = (key: string): void => {
    const spec = SIZES[key];
    if (!spec || !frame) return;
    buttons.forEach((b) => {
      b.setAttribute('aria-checked', String(b.dataset.size === key));
      b.tabIndex = b.dataset.size === key ? 0 : -1;
    });
    pics.forEach((p) => { p.hidden = p.dataset.pic !== key; });
    frame.style.setProperty('--len', String(spec.length));
    const write = (f: string, v: string): void => {
      const el = root.querySelector<HTMLElement>(`[data-f="${f}"]`);
      if (el) el.textContent = v;
    };
    write('cap', spec.capacity);
    write('dim', `${spec.length} × 32 mm`);
    write('vol', spec.volume);
  };
  buttons.forEach((b, i) => {
    b.addEventListener('click', () => set(b.dataset.size ?? '100'));
    b.addEventListener('keydown', (e) => {
      const dir = e.key === 'ArrowRight' ? 1 : e.key === 'ArrowLeft' ? -1 : 0;
      if (!dir) return;
      e.preventDefault();
      const next = buttons[(i + dir + buttons.length) % buttons.length];
      next.focus();
      set(next.dataset.size ?? '100');
    });
  });
  set('100');
}
