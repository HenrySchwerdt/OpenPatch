/** Loads three.js and the CAD meshes only after the user asks for 3D. Keeps the page's JS tiny. */
export function initViewerLauncher(reduced: boolean): void {
  const root = document.querySelector<HTMLElement>('[data-viewer]');
  const start = root?.querySelector<HTMLButtonElement>('.viewer-start');
  if (!root || !start) return;
  let started = false;
  const launch = async (): Promise<void> => {
    if (started) return;
    started = true;
    start.disabled = true;
    start.textContent = 'Loading…';
    const status = root.querySelector<HTMLElement>('.viewer-status');
    try {
      const { mountViewer } = await import('../viewer/mount');
      await mountViewer(root, reduced);
    } catch (err) {
      started = false;
      start.disabled = false;
      start.textContent = 'View in 3D';
      if (status) status.textContent = 'The 3D model could not be loaded. The renders above show the same shell.';
      console.error(err);
    }
  };
  start.addEventListener('click', () => void launch());
}
