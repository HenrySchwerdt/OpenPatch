// Step viewer for the build guide. Without JavaScript every step is shown as a long list; with it, one step at a time.
export {};
const guide = document.querySelector<HTMLElement>('[data-guide]');
const steps = guide ? [...guide.querySelectorAll<HTMLElement>('[data-step]')] : [];
if (guide && steps.length) {
  const bar = guide.querySelector<HTMLElement>('[data-guide-bar]');
  const nav = guide.querySelector<HTMLElement>('[data-guide-nav]');
  const prev = guide.querySelector<HTMLButtonElement>('[data-prev]');
  const next = guide.querySelector<HTMLButtonElement>('[data-next]');
  const pos = guide.querySelector<HTMLElement>('[data-pos]');
  const fill = guide.querySelector<HTMLElement>('.progress i');
  const meter = guide.querySelector<HTMLElement>('.progress');
  const dots = [...guide.querySelectorAll<HTMLButtonElement>('[data-goto]')];
  let cur = 0;

  const show = (i: number, focus = false): void => {
    cur = Math.max(0, Math.min(steps.length - 1, i));
    steps.forEach((s, k) => s.classList.toggle('on', k === cur));
    dots.forEach((d, k) => {
      if (k === cur) d.setAttribute('aria-current', 'step'); else d.removeAttribute('aria-current');
      d.classList.toggle('done', k < cur);
    });
    if (fill) fill.style.width = `${((cur + 1) / steps.length) * 100}%`;
    meter?.setAttribute('aria-valuenow', String(cur + 1));
    if (pos) pos.textContent = `Step ${cur + 1} of ${steps.length}`;
    if (prev) prev.disabled = cur === 0;
    if (next) { next.disabled = cur === steps.length - 1; next.textContent = cur === steps.length - 1 ? 'Last step' : 'Next step'; }
    const strip = dots[cur]?.closest<HTMLElement>('.dots');
    if (strip && dots[cur]) strip.scrollLeft = dots[cur].offsetLeft - strip.clientWidth / 2 + dots[cur].clientWidth / 2;
    try { history.replaceState(null, '', `#${steps[cur].id}`); } catch { /* ignore */ }
    if (focus) {
      const h = steps[cur].querySelector<HTMLElement>('h2');
      if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
      const top = guide.getBoundingClientRect().top + window.scrollY - 70;
      if (window.scrollY > top) window.scrollTo({ top, behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth' });
    }
  };

  guide.classList.add('live');
  if (bar) bar.hidden = false;
  if (nav) nav.hidden = false;
  const fromHash = steps.findIndex((s) => `#${s.id}` === location.hash);
  show(fromHash >= 0 ? fromHash : 0);
  prev?.addEventListener('click', () => show(cur - 1, true));
  next?.addEventListener('click', () => show(cur + 1, true));
  dots.forEach((d, k) => d.addEventListener('click', () => show(k, true)));
  guide.addEventListener('keydown', (e) => {
    const t = e.target as HTMLElement;
    if (/^(INPUT|SELECT|TEXTAREA)$/.test(t.tagName) || e.altKey || e.ctrlKey || e.metaKey) return;
    if (e.key === 'ArrowRight') { show(cur + 1, true); e.preventDefault(); }
    if (e.key === 'ArrowLeft') { show(cur - 1, true); e.preventDefault(); }
  });
  window.addEventListener('hashchange', () => { const k = steps.findIndex((s) => `#${s.id}` === location.hash); if (k >= 0 && k !== cur) show(k); });
}
