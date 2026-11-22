import { build as viteBuild, loadEnv } from 'vite';
import { build as esbuild } from 'esbuild';
import { readFile, writeFile } from 'node:fs/promises';
import process from 'node:process';

const mode = process.env.BUILD_MODE ?? 'production';
if (!['production', 'staging'].includes(mode)) throw new Error('BUILD_MODE must be production or staging.');
const env = loadEnv(mode, process.cwd(), 'VITE_');
if (mode === 'staging' && (!env.VITE_SUPABASE_URL || !env.VITE_SUPABASE_PUBLISHABLE_KEY || !env.VITE_API_BASE_URL)) {
  throw new Error('Staging build needs its Supabase URL, publishable key and API URL.');
}

await viteBuild({ mode });
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

const manifestPath = 'dist/manifest.json';
const manifest = JSON.parse(await readFile(manifestPath, 'utf8'));
const hostOrigins = [env.VITE_SUPABASE_URL, env.VITE_API_BASE_URL].filter(Boolean).map((value) => {
  const url = new URL(value);
  if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['127.0.0.1', 'localhost'].includes(url.hostname))) {
    throw new Error('Cloud URLs must use HTTPS, except loopback development URLs.');
  }
  if (mode === 'staging' && url.protocol !== 'https:') throw new Error('Staging cloud URLs must use HTTPS.');
  return `${url.origin}/*`;
});
if (hostOrigins.length) {
  manifest.host_permissions = [...new Set(hostOrigins)];
  manifest.permissions.push('identity');
}
await writeFile(manifestPath, `${JSON.stringify(manifest, null, 2)}\n`);
