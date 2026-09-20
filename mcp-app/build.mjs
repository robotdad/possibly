import { build } from 'esbuild';
import { readFile, readdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
const root = new URL('.', import.meta.url);
const result = await build({
  absWorkingDir: root.pathname,
  entryPoints: ['app.js'],
  bundle: true,
  minify: true,
  write: false,
  format: 'esm',
  target: 'es2022',
  legalComments: 'inline',
  metafile: true,
});
const nativeDashboard = await readFile(new URL('../src/possibly/dashboard.html', root), 'utf8');
const nativeController = nativeDashboard.match(/<script>([\s\S]*?)<\/script>/);
if (!nativeController) throw new Error('The native Possibly dashboard has no inline controller.');
let nativeControllerSource = nativeController[1].replace(
  "history.replaceState(null,'',location.pathname);",
  "try{history.replaceState(null,'',location.pathname)}catch{}",
);
if (nativeControllerSource === nativeController[1]) {
  throw new Error('Could not make opaque-frame history replacement safe.');
}
// This is deliberately the native document, stylesheet, and controller. The only
// inserted code supplies storage fallback plus the public-library MCP transport.
const storageFallback = `<script>
for (const name of ['localStorage','sessionStorage']) {
  try { void window[name].length; } catch {
    const values = new Map();
    Object.defineProperty(window, name, { configurable: true, value: {
      getItem: key => values.has(String(key)) ? values.get(String(key)) : null,
      setItem: (key, value) => values.set(String(key), String(value)),
      removeItem: key => values.delete(String(key)),
      clear: () => values.clear(),
    }});
  }
}
if (!crypto.randomUUID) {
  crypto.randomUUID = () => Array.from(
    crypto.getRandomValues(new Uint8Array(16)),
    value => value.toString(16).padStart(2, '0'),
  ).join('');
}
</script>`;
const script=result.outputFiles[0].text.replaceAll('</script','<\\/script');
const controllerSource = JSON.stringify(nativeControllerSource).replaceAll('</script', '<\\/script');
const template = nativeDashboard.replace(
  nativeController[0],
  () =>
    `${storageFallback}<script>window.PossiblyDashboardStart=()=>{const controller=document.createElement('script');controller.textContent=${controllerSource};document.body.append(controller)}</script><script type="module">${script}</script>`,
);
await writeFile(new URL('../src/possibly/mcp_app.html',root),template);
const packages = new Set();
for (const input of Object.keys(result.metafile.inputs)) {
  const pieces = path.resolve(input).split(`${path.sep}node_modules${path.sep}`);
  if (pieces.length < 2) continue;
  const tail = pieces.at(-1).split(path.sep);
  packages.add(pieces.slice(0,-1).join(`${path.sep}node_modules${path.sep}`)+`${path.sep}node_modules${path.sep}`+tail.slice(0,tail[0].startsWith('@') ? 2 : 1).join(path.sep));
}
let licenses = 'Third-party notices for the bundled Possibly MCP Apps view\n\n';
for (const directory of [...packages].sort()) {
  const metadata=JSON.parse(await readFile(path.join(directory,'package.json'),'utf8'));
  const license=(await readdir(directory)).find(name => /^licen[cs]e(?:\..*)?$/i.test(name));
  if(!license)throw new Error(`Missing license for ${metadata.name}`);
  licenses += `${metadata.name} ${metadata.version}\n${await readFile(path.join(directory,license),'utf8')}\n\n`;
}
await writeFile(new URL('../src/possibly/mcp_app.LICENSE.txt',import.meta.url),licenses);
