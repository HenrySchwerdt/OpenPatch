import './styles/tokens.css';
import './styles/site.css';
import { initPicker } from './lib/picker';
import { initStory } from './lib/story';
import { initReveal } from './lib/reveal';
import { initViewerLauncher } from './lib/viewer-launcher';

document.documentElement.classList.add('js');
const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)');

initReveal(reducedMotion.matches);
initPicker();
initStory(reducedMotion);
initViewerLauncher(reducedMotion.matches);
