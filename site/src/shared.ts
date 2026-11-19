import './site.css';

const root = document.documentElement;

// ---- theme: auto -> light -> dark
const MODES = ['auto', 'light', 'dark'] as const;
type Mode = (typeof MODES)[number];
const label: Record<Mode, string> = { auto: 'Auto', light: 'Light', dark: 'Dark' };
function currentMode(): Mode {
  const t = root.getAttribute('data-theme');
  return t === 'light' || t === 'dark' ? t : 'auto';
}
const toggle = document.querySelector<HTMLButtonElement>('[data-theme-toggle]');
function paint(): void {
  const m = currentMode();
  if (toggle?.firstElementChild) {
    toggle.firstElementChild.textContent = label[m];
    toggle.setAttribute('aria-label', `Colour theme: ${label[m].toLowerCase()}. Activate to change.`);
  }
}
toggle?.addEventListener('click', () => {
  const next = MODES[(MODES.indexOf(currentMode()) + 1) % 3];
  if (next === 'auto') root.removeAttribute('data-theme');
  else root.setAttribute('data-theme', next);
  try {
    if (next === 'auto') localStorage.removeItem('op-theme');
    else localStorage.setItem('op-theme', next);
  } catch { /* storage blocked */ }
  paint();
});
paint();

// ---- mobile menu
const menu = document.querySelector<HTMLButtonElement>('[data-menu]');
const nav = document.getElementById('mainnav');
const setMenu = (open: boolean): void => {
  nav?.classList.toggle('open', open);
  menu?.setAttribute('aria-expanded', String(open));
};
menu?.addEventListener('click', () => setMenu(!nav?.classList.contains('open')));
nav?.addEventListener('click', (e) => { if ((e.target as HTMLElement).closest('a')) setMenu(false); });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape' && nav?.classList.contains('open')) { setMenu(false); menu?.focus(); } });

// ---- generic table filter chips: [data-filter-group="k"] buttons[data-filter] + table[data-filter-table="k"] rows[data-k]
for (const group of document.querySelectorAll<HTMLElement>('[data-filter-group]')) {
  const key = group.dataset.filterGroup ?? '';
  const table = document.querySelector<HTMLElement>(`[data-filter-table="${key}"]`);
  const buttons = [...group.querySelectorAll<HTMLButtonElement>('[data-filter]')];
  for (const b of buttons) {
    b.addEventListener('click', () => {
      for (const x of buttons) x.setAttribute('aria-pressed', String(x === b));
      table?.querySelectorAll<HTMLElement>('tbody tr').forEach((tr) => { tr.hidden = !!b.dataset.filter && tr.dataset[key] !== b.dataset.filter; });
    });
  }
}
