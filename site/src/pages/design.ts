// Loads three.js and the meshes only when the visitor asks for 3D. The page itself ships no 3D code.
export {};

// ---- scroll story: the sticky image follows the chapter in the middle of the viewport
const story = document.querySelector<HTMLElement>('[data-story]');
if (story && 'IntersectionObserver' in window) {
  const imgs = [...story.querySelectorAll<HTMLElement>('.story-img')];
  const chs = [...story.querySelectorAll<HTMLElement>('.chapter')];
  const set = (i: number): void => {
    imgs.forEach((el, k) => el.classList.toggle('on', k === i));
    chs.forEach((el, k) => el.classList.toggle('on', k === i));
  };
  const io = new IntersectionObserver((entries) => {
    for (const e of entries) if (e.isIntersecting) set(Number((e.target as HTMLElement).dataset.i));
  }, { rootMargin: '-45% 0px -45% 0px' });
  chs.forEach((c) => io.observe(c));
}
const root = document.querySelector<HTMLElement>('[data-viewer]');
const start = root?.querySelector<HTMLButtonElement>('.viewer-start');
if (root && start) {
  let started = false;
  start.addEventListener('click', async () => {
    if (started) return;
    started = true;
    start.disabled = true;
    start.textContent = 'Loading…';
    const status = root.querySelector<HTMLElement>('.viewer-status');
    try {
      const { mountViewer } = await import('../viewer/mount');
      await mountViewer(root);
    } catch (err) {
      started = false;
      start.disabled = false;
      start.textContent = 'Load 3D model';
      if (status) status.textContent = 'The 3D model could not be loaded. The top view and parts table below still show the design.';
      console.error(err);
    }
  });
}
