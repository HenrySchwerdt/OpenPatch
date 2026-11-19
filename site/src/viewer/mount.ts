import {
  AmbientLight, Box3, BufferGeometry, Color, DirectionalLight, EdgesGeometry, Group, HemisphereLight, LineBasicMaterial, LineSegments,
  Mesh, MeshStandardMaterial, Object3D, PerspectiveCamera, PMREMGenerator, Raycaster, Scene, Spherical, Vector2, Vector3, WebGLRenderer,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

interface PartInfo {
  id: string; name: string; category?: string; process?: string; lockNo?: number | null; note?: string; partNumber?: string; vendor?: string; model?: string;
  url: string | null; confidence?: string; material?: string; usedFor?: string; frame?: string; mass?: number | null; bytes?: number; bbox?: number[]; tris?: number; datasheet?: string; verified?: unknown; source?: string; dims?: unknown; position?: number[] | null;
}
interface Manifest {
  source: string; generated: string; catalogNote: string;
  sizes: Record<string, { parts: PartInfo[] }>;
  catalog: PartInfo[] | null;
  assembly: { url: string; bytes: number; from: string } | null;
}
interface Live { info: PartInfo; obj: Object3D; mat: MeshStandardMaterial; centre: Vector3; label: HTMLButtonElement; item: HTMLButtonElement; edges: LineSegments[] }

const COLORS: Record<string, number> = { housing: 0xd6d1c0, fluid: 0x7fb6d9, drive: 0xd9a441, interface: 0xb08fc7, component: 0x9aa7b3, part: 0xbfc5cb };

const cssVar = (n: string): string => getComputedStyle(document.documentElement).getPropertyValue(n).trim() || '#000';
const el = <K extends keyof HTMLElementTagNameMap>(tag: K, cls = '', text = ''): HTMLElementTagNameMap[K] => {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text) e.textContent = text;
  return e;
};

export async function mountViewer(host: HTMLElement): Promise<void> {
  const stage = host.querySelector<HTMLElement>('.viewer-stage');
  const canvas = host.querySelector<HTMLCanvasElement>('.viewer-canvas');
  const panel = host.querySelector<HTMLElement>('.viewer-panel');
  const labelsEl = host.querySelector<HTMLElement>('.viewer-labels');
  const placeholder = host.querySelector<HTMLElement>('.viewer-placeholder');
  const sourceNote = document.querySelector<HTMLElement>('[data-viewer-source]');
  const status = host.querySelector<HTMLElement>('.viewer-status');
  if (!stage || !canvas || !panel || !labelsEl || !placeholder) throw new Error('viewer markup missing');

  const manifestUrl = host.dataset.manifest ?? 'models/manifest.json';
  const siteRoot = host.dataset.root ?? './';
  const manifest = (await (await fetch(manifestUrl)).json()) as Manifest;

  const renderer = new WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  const scene = new Scene();
  scene.environment = new PMREMGenerator(renderer).fromScene(new RoomEnvironment(), 0.04).texture;
  scene.add(new HemisphereLight(0xffffff, 0x8892a0, 1.1));
  scene.add(new AmbientLight(0xffffff, 0.35));
  const key = new DirectionalLight(0xffffff, 1.6);
  key.position.set(-40, 90, 60);
  scene.add(key);
  const fill = new DirectionalLight(0xffffff, 0.5);
  fill.position.set(60, 20, -50);
  scene.add(fill);

  const camera = new PerspectiveCamera(30, 1, 5, 900);
  camera.position.set(-90, 80, 110);
  const controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 40;
  controls.maxDistance = 320;
  controls.enablePan = false;

  const group = new Group();
  group.rotation.x = -Math.PI / 2; // CAD z-up -> three y-up
  scene.add(group);

  const loader = new GLTFLoader();
  const lineMat = new LineBasicMaterial({ color: new Color(cssVar('--ink')), transparent: true, opacity: 0.45 });
  const recolour = (): void => { lineMat.color.set(cssVar('--ink')); wake(); };
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change', recolour);
  new MutationObserver(recolour).observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });

  let live: Live[] = [];
  const sizeInputs = [...panel.querySelectorAll<HTMLInputElement>('input[name="vsize"]')];
  const explode = panel.querySelector<HTMLInputElement>('.explode');
  const showLabels = panel.querySelector<HTMLInputElement>('.show-labels');
  const list = panel.querySelector<HTMLElement>('.partlist');
  const infoEl = panel.querySelector<HTMLElement>('.partinfo');
  const mid = new Vector3();

  function describe(p: PartInfo): void {
    if (!infoEl) return;
    infoEl.replaceChildren();
    infoEl.append(el('h4', '', p.name));
    const dl = el('dl');
    const add = (k: string, v: string | undefined | null, href?: string): void => {
      if (!v) return;
      const d = el('div');
      d.append(el('dt', '', k));
      const dd = el('dd');
      if (href) { const a = el('a', '', v); a.href = href; a.rel = 'noopener'; dd.append(a); } else dd.textContent = v;
      d.append(dd);
      dl.append(d);
    };
    add('Part number', p.partNumber || p.id);
    add('Vendor / source', p.vendor || p.source);
    add('Process', p.process);
    add('Category', p.category);
    if (p.lockNo) {
      const row = document.querySelector<HTMLElement>(`tr[data-lock="${p.lockNo}"]`);
      add('Parts lock row', `#${p.lockNo}${row ? ': ' + (row.children[2]?.textContent ?? '') : ''}`, `${siteRoot}docs/parts-lock/`);
    }
    if (p.bbox) add('Bounding box', `${p.bbox.join(' × ')} mm`);
    if (p.dims) add('Dimensions', Array.isArray(p.dims) ? `${p.dims.join(' × ')} mm` : String(p.dims));
    add('Model', p.model ?? (p.confidence ? `component library, confidence: ${p.confidence}` : 'component library'));
    add('Material', p.material);
    add('Used for', p.usedFor);
    if (p.mass) add('Mass (estimate)', `${p.mass} g`);
    add('Frame', p.frame);
    add('Note', p.note);
    if (p.datasheet) add('Datasheet', 'Open datasheet', p.datasheet);
    infoEl.append(dl);
  }

  function select(l: Live | null): void {

    for (const x of live) {
      const on = x === l;
      x.label.setAttribute('aria-pressed', String(on));
      x.item.setAttribute('aria-pressed', String(on));
      x.mat.emissive.set(on ? 0x2f6fb0 : 0x000000);
      x.mat.emissiveIntensity = on ? 0.55 : 0;
    }
    if (l) describe(l.info);
    else infoEl?.replaceChildren(el('p', 'muted', 'Select a part to see its data.'));
    wake();
  }

  function build(parts: { info: PartInfo; obj: Object3D }[]): void {
    group.clear();
    labelsEl!.replaceChildren();
    list!.replaceChildren();
    live = [];
    for (const { info, obj } of parts) {
      const mat = new MeshStandardMaterial({ color: COLORS[info.category ?? 'part'] ?? COLORS.part, roughness: 0.6, metalness: 0.05, transparent: info.id.endsWith('_top'), opacity: info.id.endsWith('_top') ? 0.4 : 1 });
      const edges: LineSegments[] = [];
      obj.traverse((o) => {
        if (!(o instanceof Mesh)) return;
        const g = o.geometry as BufferGeometry;
        g.computeVertexNormals();
        o.material = mat;
        if ((g.index?.count ?? 0) / 3 < 160000) {
          const e = new LineSegments(new EdgesGeometry(g, 35), lineMat);
          o.add(e);
          edges.push(e);
        }
      });
      const label = el('button', 'vlabel', (info.partNumber || info.name).replace(/^OP-\d+_/, ''));
      label.type = 'button';
      label.setAttribute('aria-pressed', 'false');
      label.setAttribute('aria-label', `${info.name}, ${info.partNumber ?? ''}`);
      const item = el('button');
      item.type = 'button';
      item.setAttribute('aria-pressed', 'false');
      item.append(document.createTextNode(info.name));
      if (info.partNumber) item.append(el('span', 'pn', info.partNumber));
      const li = el('li');
      li.append(item);
      list!.append(li);
      labelsEl!.append(label);
      group.add(obj);
      const l: Live = { info, obj, mat, centre: new Vector3(), label, item, edges };
      label.addEventListener('click', () => select(l));
      item.addEventListener('click', () => select(l));
      live.push(l);
    }
    const box = new Box3().setFromObject(group);
    box.getCenter(mid);
    for (const l of live) new Box3().setFromObject(l.obj).getCenter(l.centre);
    applyExplode();
    select(null);
  }

  function applyExplode(): void {
    const f = Number(explode?.value ?? 0) / 100;
    group.updateMatrixWorld(true);
    for (const l of live) {
      // offsets in CAD space (z up): layers spread along z, parts also drift outwards in the plane
      const d = new Vector3(l.centre.x - mid.x, l.centre.y - mid.y, l.centre.z - mid.z);
      // centres are measured in world space (after the group rotation); convert the offset back to local CAD axes
      const local = new Vector3(d.x, -d.z, d.y);
      l.obj.position.set(local.x * 0.45 * f, local.y * 0.45 * f, local.z * 3.2 * f + (l.info.id.endsWith('_top') ? 30 * f : 0) + (l.info.id.endsWith('_bottom') ? -8 * f : 0));
    }
    wake();
  }

  async function loadSize(size: string): Promise<void> {
    if (status) status.textContent = 'Loading meshes…';
    const parts: { info: PartInfo; obj: Object3D }[] = [];
    if (manifest.assembly) {
      const gltf = await loader.loadAsync(siteRoot + manifest.assembly.url);
      const nodes = gltf.scene.children.length ? [...gltf.scene.children] : [gltf.scene];
      for (const n of nodes) {
        const cat = (manifest.catalog ?? []).find((c) => c.id === n.name || n.name.includes(c.id));
        parts.push({ info: cat ?? { id: n.name || 'part', name: n.name || 'Part', url: null, model: 'assembly glTF' }, obj: n });
      }
    } else {
      const src = manifest.sizes[size]?.parts ?? [];
      const loaded = await Promise.all(src.map(async (p) => ({ info: p, gltf: await loader.loadAsync(siteRoot + (p.url ?? '')) })));
      for (const { info, gltf } of loaded) {
        const cat = manifest.catalog?.find((c) => c.lockNo && c.lockNo === info.lockNo);
        parts.push({ info: cat ? { ...info, vendor: cat.vendor || info.vendor, datasheet: cat.datasheet } : info, obj: gltf.scene });
      }
      for (const c of manifest.catalog ?? []) {
        if (!c.url || !c.position || src.some((p) => p.lockNo && p.lockNo === c.lockNo)) continue;
        const g = await loader.loadAsync(siteRoot + c.url);
        g.scene.position.fromArray(c.position);
        parts.push({ info: c, obj: g.scene });
      }
    }
    build(parts);
    // fill the "3D model" column of the parts table
    for (const cell of document.querySelectorAll<HTMLElement>('[data-model-for]')) {
      const hit = live.find((l) => String(l.info.lockNo ?? '') === cell.dataset.modelFor);
      const lib = (manifest.catalog ?? []).filter((c) => c.url && String(c.lockNo ?? '') === cell.dataset.modelFor);
      const bits = [...(hit ? [`pod: ${hit.info.name} (generated envelope)`] : []), ...lib.map((c) => `library: ${c.id} (${c.confidence || 'catalog'})`)];
      if (bits.length) cell.textContent = bits.join('; ');
    }
    controls.target.set(0, 4, 0);
    resetCamera();
    if (status) status.textContent = '';
  }

  const resetCamera = (): void => {
    const box = new Box3().setFromObject(group);
    const c = box.getCenter(new Vector3());
    controls.target.copy(c);
    const r = Math.max(80, box.getSize(new Vector3()).length() * 1.5);
    camera.position.set(c.x - 0.55 * r, c.y + 0.6 * r, c.z + 0.8 * r);
    controls.update();
  };

  // ---- rendering loop (only while visible)
  let raf = 0;
  let visible = true;
  const proj = new Vector3();
  const tick = (): void => {
    raf = 0;
    if (!visible) return;
    controls.update();
    renderer.render(scene, camera);
    const w = canvas.clientWidth, h = canvas.clientHeight;
    const on = showLabels?.checked !== false && w > 520;
    for (const l of live) {
      l.label.hidden = !on;
      if (!on) continue;
      group.updateMatrixWorld();
      proj.copy(new Box3().setFromObject(l.obj).getCenter(new Vector3())).project(camera);
      l.label.style.left = `${(proj.x * 0.5 + 0.5) * w}px`;
      l.label.style.top = `${(-proj.y * 0.5 + 0.5) * h}px`;
    }
    raf = requestAnimationFrame(tick);
  };
  function wake(): void { if (!raf && visible) raf = requestAnimationFrame(tick); }
  const resize = (): void => {
    const w = canvas.clientWidth, h = canvas.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    wake();
  };
  new ResizeObserver(resize).observe(canvas);
  new IntersectionObserver((e) => { visible = e.some((x) => x.isIntersecting); wake(); }).observe(stage);
  controls.addEventListener('change', wake);

  // ---- interaction
  const ray = new Raycaster();
  let down: Vector2 | null = null;
  canvas.addEventListener('pointerdown', (e) => { down = new Vector2(e.clientX, e.clientY); });
  canvas.addEventListener('pointerup', (e) => {
    if (!down || down.distanceTo(new Vector2(e.clientX, e.clientY)) > 4) return;
    const r = canvas.getBoundingClientRect();
    ray.setFromCamera(new Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1), camera);
    const hit = ray.intersectObjects(live.map((l) => l.obj), true)[0];
    select(hit ? live.find((l) => { let o: Object3D | null = hit.object; while (o) { if (o === l.obj) return true; o = o.parent; } return false; }) ?? null : null);
  });
  canvas.addEventListener('keydown', (e) => {
    const off = camera.position.clone().sub(controls.target);
    const s = new Spherical().setFromVector3(off);
    const step = 0.12;
    if (e.key === 'ArrowLeft') s.theta -= step; else if (e.key === 'ArrowRight') s.theta += step;
    else if (e.key === 'ArrowUp') s.phi = Math.max(0.1, s.phi - step); else if (e.key === 'ArrowDown') s.phi = Math.min(Math.PI - 0.1, s.phi + step);
    else if (e.key === '+' || e.key === '=') s.radius = Math.max(controls.minDistance, s.radius * 0.9); else if (e.key === '-') s.radius = Math.min(controls.maxDistance, s.radius * 1.1);
    else if (e.key === 'Escape') { select(null); return; } else return;
    e.preventDefault();
    camera.position.copy(controls.target).add(new Vector3().setFromSpherical(s));
    controls.update();
    wake();
  });
  explode?.addEventListener('input', applyExplode);
  showLabels?.addEventListener('change', () => { if (showLabels.checked) wake(); else for (const l of live) l.label.hidden = true; });
  let busy = false;
  for (const r of sizeInputs) {
    r.addEventListener('change', async () => {
      if (busy || manifest.assembly) return;
      busy = true;
      try { await loadSize(r.value); } finally { busy = false; }
    });
  }

  // ---- component library view: every catalogued part on its own (glTF is metres, Y up)
  const modeBox = panel.querySelector<HTMLElement>('.mode-pick');
  const modeInputs = [...panel.querySelectorAll<HTMLInputElement>('input[name="vmode"]')];
  const sizeBox = panel.querySelector<HTMLElement>('.size-pick');
  const explodeLabel = explode?.closest('label');
  const comp = new Group();
  scene.add(comp);
  const library = (manifest.catalog ?? []).filter((c) => c.url).sort((a, b) => (a.lockNo ?? 99) - (b.lockNo ?? 99) || a.name.localeCompare(b.name));
  if (library.length && modeBox) modeBox.hidden = false;

  async function showComponent(c: PartInfo): Promise<void> {
    if (status) status.textContent = 'Loading part…';
    const gltf = await loader.loadAsync(siteRoot + (c.url ?? ''));
    const obj = gltf.scene;
    const size = new Box3().setFromObject(obj).getSize(new Vector3());
    if (Math.max(size.x, size.y, size.z) < 1) obj.scale.setScalar(1000); // metres -> mm
    obj.updateMatrixWorld(true);
    const box = new Box3().setFromObject(obj);
    obj.position.sub(box.getCenter(new Vector3()));
    obj.traverse((o) => {
      if (!(o instanceof Mesh)) return;
      const g = o.geometry as BufferGeometry;
      if ((g.index?.count ?? g.attributes.position.count) / 3 < 120000) o.add(new LineSegments(new EdgesGeometry(g, 35), lineMat));
    });
    comp.clear();
    comp.add(obj);
    const r = Math.max(12, new Box3().setFromObject(comp).getSize(new Vector3()).length() * 2.2);
    controls.target.set(0, 0, 0);
    camera.position.set(-0.5 * r, 0.6 * r, 0.8 * r);
    controls.update();
    describe(c);
    if (status) status.textContent = '';
    wake();
  }

  function showLibrary(): void {
    group.visible = false;
    labelsEl!.replaceChildren();
    for (const l of live) l.label.hidden = true;
    if (sizeBox) sizeBox.hidden = true;
    if (explodeLabel) explodeLabel.hidden = true;
    controls.minDistance = 4;
    list!.replaceChildren();
    for (const c of library) {
      const item = el('button');
      item.type = 'button';
      item.setAttribute('aria-pressed', 'false');
      item.append(document.createTextNode(c.name.length > 60 ? `${c.name.slice(0, 57)}...` : c.name));
      item.append(el('span', 'pn', c.id));
      item.addEventListener('click', () => {
        list!.querySelectorAll('button').forEach((b) => b.setAttribute('aria-pressed', String(b === item)));
        void showComponent(c);
      });
      const li = el('li');
      li.append(item);
      list!.append(li);
    }
    infoEl?.replaceChildren(el('p', 'muted', `Select one of ${library.length} catalogued components. Each is built from the vendor drawing or datasheet; the confidence level is shown in its data.`));
  }

  for (const m of modeInputs) {
    m.addEventListener('change', async () => {
      if (!m.checked) return;
      if (m.value === 'library') { showLibrary(); return; }
      comp.clear();
      group.visible = true;
      if (sizeBox) sizeBox.hidden = false;
      if (explodeLabel) explodeLabel.hidden = false;
      controls.minDistance = 40;
      await loadSize(sizeInputs.find((r) => r.checked)?.value ?? '100');
    });
  }

  placeholder.hidden = true;
  canvas.hidden = false;
  panel.hidden = false;
  host.classList.add('live');
  await loadSize('100');
  resize();
  tick();
  if (sourceNote) {
    sourceNote.textContent = manifest.assembly
      ? `Model source: assembly glTF (${manifest.assembly.from}). ${manifest.catalogNote}`
      : manifest.catalog
        ? `Pod view: generated CAD envelopes (final assembly not yet available). Component library view: ${manifest.catalogNote}, each with a confidence level (datasheet, estimated or placeholder).`
        : 'Model source: generated CAD (mechanical/out), simplified envelopes for fit and interference checks, not vendor-accurate. Motor, gears, sensor board and valves have no model yet.';
  }
  host.dataset.ready = 'true';
}
