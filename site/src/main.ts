import '@fontsource-variable/inter-tight/wght.css';
import '@fontsource/jetbrains-mono/latin-400.css';
import '@fontsource/jetbrains-mono/latin-500.css';
import './styles/tokens.css';
import './styles/base.css';
import './styles/hero.css';
import './styles/sections.css';

import { bindSizeSwitches } from './lib/state';
import { initSpec } from './lib/spec';
import { initNav, initReveal, initTheme } from './lib/ui';

initTheme();
initNav();
bindSizeSwitches();
initSpec();
initReveal();

// three.js wird als eigener Chunk nachgeladen, damit Text und Layout sofort stehen.
void import('./three/stage')
  .then((m) => m.initStage())
  .catch((err: unknown) => {
    console.error('[OpenPatch] 3D-Modul konnte nicht geladen werden', err);
    const fb = document.getElementById('stage-fallback');
    if (fb) fb.hidden = false;
  });
