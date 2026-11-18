import { isSizeId, type SizeId } from './sizes';

type Listener = (id: SizeId) => void;

let current: SizeId = 'OP-100';
const listeners = new Set<Listener>();

export const getSize = (): SizeId => current;

export function setSize(next: SizeId): void {
  if (!isSizeId(next) || next === current) return;
  current = next;
  listeners.forEach((l) => l(current));
}

export function onSize(listener: Listener): void {
  listeners.add(listener);
  listener(current);
}

/** Verdrahtet alle [data-size-switch]-Gruppen mit dem gemeinsamen Zustand. */
export function bindSizeSwitches(): void {
  const groups = document.querySelectorAll<HTMLElement>('[data-size-switch]');
  groups.forEach((group) => {
    group.addEventListener('click', (e) => {
      const btn = (e.target as HTMLElement).closest<HTMLButtonElement>('button[data-size]');
      if (btn && isSizeId(btn.dataset.size)) setSize(btn.dataset.size);
    });
  });
  onSize((id) => {
    groups.forEach((group) =>
      group.querySelectorAll<HTMLButtonElement>('button[data-size]').forEach((b) => {
        b.setAttribute('aria-pressed', String(b.dataset.size === id));
      }),
    );
    document.getElementById('stage-size-tag')!.textContent = id;
  });
}
