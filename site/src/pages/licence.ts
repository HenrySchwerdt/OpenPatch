// Recoupment calculator (draft terms of COMMERCIAL-LICENSE.md section 3a, illustrative only).
export {};
const form = document.querySelector<HTMLElement>('[data-calc]');
const out = document.querySelector<HTMLElement>('[data-calc-out]');
if (form && out) {
  const eur = new Intl.NumberFormat('en', { style: 'currency', currency: 'EUR', maximumFractionDigits: 2 });
  const int = new Intl.NumberFormat('en', { maximumFractionDigits: 0 });
  const val = (k: string): number => Math.max(0, Number(form.querySelector<HTMLInputElement>(`[data-k="${k}"]`)?.value) || 0);
  const set = (k: string, v: string): void => { const e = out.querySelector(`[data-o="${k}"]`); if (e) e.textContent = v; };
  const update = (): void => {
    const recov = Math.max(0, val('inv') - val('levyFunded'));
    const total = recov * (1 + val('ret') / 100);
    const cost = val('cost');
    const price = cost * 1.3;
    const margin = price - cost;
    const per = margin * (val('share') / 100);
    const coll = Math.min(total, per * val('units'));
    set('recov', eur.format(recov));
    set('total', eur.format(total));
    set('price', eur.format(price));
    set('margin', eur.format(margin));
    set('per', eur.format(per));
    set('keep', eur.format(margin - per));
    set('levy', eur.format(price * 0.05));
    set('coll', eur.format(coll));
    set('pct', total ? `${Math.round((coll / total) * 100)} %` : 'n/a');
    set('need', per > 0 ? int.format(Math.ceil(total / per)) : 'never (no recoupment per unit)');
    const bar = out.querySelector<HTMLElement>('[data-bar] span');
    if (bar) bar.style.width = `${total ? Math.min(100, (coll / total) * 100) : 0}%`;
  };
  form.addEventListener('input', update);
  form.addEventListener('submit', (e) => e.preventDefault());
  update();
}
