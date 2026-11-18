/**
 * Scroll-driven story: writes one CSS variable (--p, 0..1) and the active beat.
 * All visual change is transform/opacity in CSS. Reduced motion shows static layout via CSS.
 */
export function initStory(reduced: MediaQueryList): void {
  const root = document.querySelector<HTMLElement>('.story');
  const track = root?.querySelector<HTMLElement>('.story-track');
  if (!root || !track) return;
  let ticking = false;
  let active = false;

  const update = (): void => {
    ticking = false;
    if (reduced.matches) { root.style.removeProperty('--p'); root.dataset.beat = '1'; return; }
    const r = track.getBoundingClientRect();
    const travel = r.height - window.innerHeight;
    const p = Math.min(1, Math.max(0, -r.top / Math.max(1, travel)));
    root.style.setProperty('--p', p.toFixed(4));
    root.dataset.beat = p < 0.22 ? '1' : p < 0.62 ? '2' : '3';
  };
  const onScroll = (): void => {
    if (!ticking) { ticking = true; requestAnimationFrame(update); }
  };
  const io = new IntersectionObserver((entries) => {
    const on = entries.some((e) => e.isIntersecting);
    if (on === active) return;
    active = on;
    if (on) { window.addEventListener('scroll', onScroll, { passive: true }); update(); }
    else window.removeEventListener('scroll', onScroll);
  }, { rootMargin: '10% 0px' });
  io.observe(track);
  reduced.addEventListener('change', update);
  root.dataset.beat = '1';
  update();
}
