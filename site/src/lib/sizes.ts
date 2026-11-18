export type SizeId = 'OP-70' | 'OP-100' | 'OP-200';

export interface SizeSpec {
  readonly id: SizeId;
  readonly units: number;
  readonly ml: number;
  readonly length: number;
  readonly width: number;
  readonly height: number;
  /** Kolbenhub in mm (spec/design-parameters.md §3) */
  readonly stroke: number;
  /** Grobe Gewichtsschätzung, leer, in g */
  readonly weightG: number;
}

export const SIZES: Readonly<Record<SizeId, SizeSpec>> = {
  'OP-70': { id: 'OP-70', units: 70, ml: 0.7, length: 38, width: 32, height: 8.5, stroke: 9.4, weightG: 10 },
  'OP-100': { id: 'OP-100', units: 100, ml: 1.0, length: 42, width: 32, height: 8.5, stroke: 13.4, weightG: 11 },
  'OP-200': { id: 'OP-200', units: 200, ml: 2.0, length: 55.4, width: 32, height: 8.5, stroke: 26.8, weightG: 15 },
};

export const SIZE_IDS = Object.keys(SIZES) as SizeId[];

export const DASH = { length: 52, width: 39, height: 14.5 } as const;

/** Auflösung: 0,35 mm / (20 · 10) = 1,75 µm pro Schritt */
export const STEP = { micrometres: 1.75, microlitres: 0.131, units: 0.0131 } as const;

export const isSizeId = (v: unknown): v is SizeId => typeof v === 'string' && v in SIZES;

const nf = new Intl.NumberFormat('de-DE', { maximumFractionDigits: 2 });
export const fmt = (n: number): string => nf.format(n);
