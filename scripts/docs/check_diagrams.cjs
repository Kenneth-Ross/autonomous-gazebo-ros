/* Validate Mermaid grammar without opening or controlling a browser. */
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '../..');
const context = vm.createContext({console, setTimeout, clearTimeout});
const bundle = fs.readFileSync(path.join(root, 'docs/site/assets/mermaid.min.js'), 'utf8');
// Mermaid's parser sanitizes labels with DOMPurify, which needs a browser DOM.
// Substitute only that function in this in-memory grammar-check VM. This is
// syntax validation, not rendering or security validation. The vendored file
// and the site's strict-mode browser renderer remain unmodified.
if (bundle.split('ah=iG()').length !== 2) throw new Error('Review parser shim after changing Mermaid version');
vm.runInContext(bundle.replace('ah=iG()', 'ah={sanitize:t=>t,addHook:()=>{}}'), context);
context.mermaid.initialize({startOnLoad: false, securityLevel: 'strict'});
(async () => {
  let count = 0;
  let invalidRejected = false;
  try { await context.mermaid.parse('flowchart LR\nA --> ['); }
  catch { invalidRejected = true; }
  if (!invalidRejected) throw new Error('Grammar checker accepted the malformed control case');
  for (const folder of ['docs', 'plans', 'deprecated']) {
    for (const file of fs.readdirSync(path.join(root, folder)).filter(file => file.endsWith('.md'))) {
      const text = fs.readFileSync(path.join(root, folder, file), 'utf8');
      for (const match of text.matchAll(/```mermaid\n([\s\S]*?)```/g)) {
        try { await context.mermaid.parse(match[1]); count++; }
        catch (error) { console.error(`${folder}/${file}: ${error.message}`); process.exitCode = 1; }
      }
    }
  }
  console.log(`Validated ${count} Mermaid diagrams`);
})();
