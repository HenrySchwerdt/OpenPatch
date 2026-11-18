export const prefersReducedMotion = (): boolean => window.matchMedia('(prefers-reduced-motion: reduce)').matches;

export function initTheme(): void {
  const root = document.documentElement;
  const btn = document.getElementById('theme-toggle') as HTMLButtonElement | null;
  if (!btn) return;
  const sync = (): void => {
    const dark = root.dataset.theme === 'dark';
    btn.setAttribute('aria-pressed', String(dark));
    btn.setAttribute('aria-label', dark ? 'Helles Design einschalten' : 'Dunkles Design einschalten');
  };
  sync();
  btn.addEventListener('click', () => {
    const next = root.dataset.theme === 'dark' ? 'light' : 'dark';
    root.dataset.theme = next;
    try {
      localStorage.setItem('op-theme', next);
    } catch {
      /* Speicher gesperrt: Auswahl gilt nur für diese Sitzung */
    }
    sync();
    window.dispatchEvent(new CustomEvent('op-theme', { detail: next }));
  });
}

export function initNav(): void {
  const toggle = document.getElementById('nav-toggle') as HTMLButtonElement | null;
  const nav = document.getElementById('site-nav');
  if (!toggle || !nav) return;
  const set = (open: boolean): void => {
    nav.classList.toggle('open', open);
    toggle.setAttribute('aria-expanded', String(open));
    toggle.setAttribute('aria-label', open ? 'Menü schließen' : 'Menü öffnen');
  };
  toggle.addEventListener('click', () => set(!nav.classList.contains('open')));
  nav.addEventListener('click', (e) => {
    if ((e.target as HTMLElement).closest('a')) set(false);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && nav.classList.contains('open')) {
      set(false);
      toggle.focus();
    }
  });
}

export function initReveal(): void {
  const items = document.querySelectorAll<HTMLElement>('.reveal');
  if (prefersReducedMotion() || !('IntersectionObserver' in window)) {
    items.forEach((el) => el.classList.add('in'));
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add('in');
          io.unobserve(entry.target);
        }
      }
    },
    { rootMargin: '0px 0px -8% 0px', threshold: 0.05 },
  );
  items.forEach((el) => io.observe(el));
}
