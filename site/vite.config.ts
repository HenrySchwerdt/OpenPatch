import { defineConfig, type Plugin } from 'vite';

const REPO = (process.env.VITE_REPO_URL || 'https://github.com/HenrySchwerdt/ai-insulin-pump').replace(/\/$/, '');

function injectRepo(): Plugin {
  return { name: 'openpatch-repo', transformIndexHtml: (html) => html.replaceAll('%REPO%', REPO) };
}

export default defineConfig({
  base: process.env.VITE_BASE || './',
  plugins: [injectRepo()],
  build: { target: 'es2022', chunkSizeWarningLimit: 700 },
  server: { host: '127.0.0.1' },
});
