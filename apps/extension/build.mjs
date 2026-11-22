import { build as viteBuild } from 'vite';
import { build as esbuild } from 'esbuild';

await viteBuild();
await esbuild({
  entryPoints: ['src/background/index.ts', 'src/content/index.ts'],
  outdir: 'dist',
  entryNames: '[dir]/index',
  bundle: true,
  format: 'iife',
  platform: 'browser',
  target: 'chrome116',
  minify: true,
});
