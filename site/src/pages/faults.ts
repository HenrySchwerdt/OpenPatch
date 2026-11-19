// Fault-code explorer: client-side filtering of the statically rendered catalogue.
export {};
const root = document.querySelector<HTMLElement>('[data-explorer]');
if (root) {
  const q = root.querySelector<HTMLInputElement>('#q');
  const layer = root.querySelector<HTMLSelectElement>('#layer');
  const fru = root.querySelector<HTMLSelectElement>('#fru');
  const sevBtns = [...root.querySelectorAll<HTMLButtonElement>('button[data-sev]')];
  const items = [...root.querySelectorAll<HTMLDetailsElement>('details.fault')];
  const count = root.querySelector<HTMLElement>('[data-count]');
  const empty = root.querySelector<HTMLElement>('[data-empty]');
  const total = items.length;

  const apply = (): void => {
    if (!q || !layer || !fru) return;
    const terms = q.value.toLowerCase().split(/\s+/).filter(Boolean);
    const sevs = sevBtns.filter((b) => b.getAttribute('aria-pressed') === 'true').map((b) => b.dataset.sev);
    let n = 0;
    for (const it of items) {
      const text = it.dataset.text ?? '';
      const ok = terms.every((t) => text.includes(t)) && (!layer.value || it.dataset.layer === layer.value) && (!fru.value || it.dataset.fru === fru.value) && (!sevs.length || sevs.includes(it.dataset.sev));
      it.hidden = !ok;
      if (ok) n++;
    }
    if (count) count.textContent = `${n} of ${total} codes shown`;
    if (empty) empty.hidden = n !== 0;
  };
  q?.addEventListener('input', apply);
  layer?.addEventListener('change', apply);
  fru?.addEventListener('change', apply);
  sevBtns.forEach((b) => b.addEventListener('click', () => { b.setAttribute('aria-pressed', String(b.getAttribute('aria-pressed') !== 'true')); apply(); }));
  root.querySelector('[data-reset]')?.addEventListener('click', () => {
    if (q) q.value = '';
    if (layer) layer.value = '';
    if (fru) fru.value = '';
    sevBtns.forEach((b) => b.setAttribute('aria-pressed', 'false'));
    apply();
    q?.focus();
  });
  let expanded = false;
  const expandBtn = root.querySelector<HTMLButtonElement>('[data-expand]');
  expandBtn?.addEventListener('click', () => {
    expanded = !expanded;
    for (const it of items) if (!it.hidden) it.open = expanded;
    expandBtn.textContent = expanded ? 'Collapse all' : 'Expand all';
  });

  // deep links: #c-1-06-001 opens that code, #q=text prefills the search
  const fromHash = (): void => {
    const h = decodeURIComponent(location.hash.slice(1));
    if (h.startsWith('q=') && q) { q.value = h.slice(2); apply(); return; }
    const t = h.startsWith('c-') ? document.getElementById(h) : null;
    if (t instanceof HTMLDetailsElement) { t.hidden = false; t.open = true; t.scrollIntoView({ block: 'center' }); }
  };
  addEventListener('hashchange', fromHash);
  fromHash();
}
