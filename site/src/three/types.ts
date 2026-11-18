import type { Group, Object3D, Vector3 } from 'three';

export type PartId = 'base' | 'battery' | 'pcb' | 'motor' | 'reservoir' | 'plunger' | 'lid';

/** Höhenversatz je Bauteil in der Explosionsansicht (mm, entlang der Bauhöhe). */
export const EXPLODE_OFFSET: Readonly<Record<PartId, number>> = {
  base: 0,
  battery: 8,
  pcb: 16,
  motor: 25,
  reservoir: 34,
  plunger: 43,
  lid: 56,
};

export const PART_LABEL: Readonly<Record<PartId, string>> = {
  base: 'Gehäuse unten · Klett',
  battery: 'Li-Po 60–90 mAh',
  pcb: 'PCB · nRF54L15',
  motor: 'Ø6 Schrittmotor',
  reservoir: 'Reservoir 16 × 5',
  plunger: 'Stadion-Kolben',
  lid: 'Gehäuse oben',
};

export interface PodModel {
  readonly group: Group;
  readonly parts: ReadonlyMap<PartId, Object3D>;
  /** Ankerpunkte (lokal, Pod-Koordinaten) für Beschriftungen */
  readonly anchors: ReadonlyMap<PartId, Vector3>;
  readonly source: 'procedural' | 'hybrid' | 'stl';
  readonly explodable: boolean;
  readonly length: number;
  readonly width: number;
  readonly height: number;
}

/** Auszug aus mechanical/out/OP-*.layout.json (CAD-Koordinaten: x ab Kante, y Breite, z oben). */
export interface CadLayout {
  length: number;
  width: number;
  x_r0: number;
  x_r1: number;
  x_s?: number;
  gear_x1?: number;
  x_end: number;
  bat_x: number;
  y_r: number;
  y_s: number;
  y_m: number;
  z_axis: number;
  z_top_inner: number;
  coil_cx: number;
  coil_cy: number;
}
