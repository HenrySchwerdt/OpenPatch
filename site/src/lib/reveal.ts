/** Fades elements in once as they enter the viewport. Cost bars animate via the .in class on their figure. */
export function initReveal(reduced: boolean): void {
  const targets = document.querySelectorAll<HTMLElement>('.reveal, .costs');
  if (reduced || !('IntersectionObserver' in window)) {
    targets.forEach((el) => el.classList.add('in'));
    return;
  }
  const io = new IntersectionObserver(
    (entries) => {
      for (const e of entries) {
        if (!e.isIntersecting) continue;
        e.target.classList.add('in');
        io.unobserve(e.target);
      }
    },
    { threshold: 0.3 },
  );
  targets.forEach((el) => io.observe(el));
}
