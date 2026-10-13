/* Reading, navigation, and source links work independently of this enhancement. */
const search = document.querySelector('#search');
const results = document.querySelector('#search-results');
let indexPromise;
let queryGeneration = 0;
search?.addEventListener('input', async () => {
  const generation = ++queryGeneration;
  const query = search.value.trim().toLowerCase();
  results.replaceChildren();
  if (query.length < 2) return;
  try {
    indexPromise ??= fetch(search.dataset.index).then(response => {
      if (!response.ok) throw new Error('Search index unavailable');
      return response.json();
    });
    const index = await indexPromise;
    if (generation !== queryGeneration) return;
    const terms = query.split(/\s+/);
    const matches = index.filter(page => terms.every(term => `${page.title} ${page.text}`.toLowerCase().includes(term)))
      .sort((a, b) => Number(a.historical) - Number(b.historical));
    const count = document.createElement('p');
    count.className = 'search-count';
    count.textContent = matches.length ? `${matches.length} pages found` : 'No matches. Try a topic, node, or port.';
    results.append(count);
    for (const page of matches.slice(0, 12)) {
      const link = document.createElement('a');
      link.href = search.dataset.root + page.path;
      link.textContent = page.title;
      const context = document.createElement('small');
      context.textContent = page.historical ? 'Historical archive' : page.path.replace('.html', '');
      link.append(context);
      results.append(link);
    }
  } catch {
    indexPromise = undefined;
    results.textContent = 'Search is unavailable. Browse the documentation menu.';
  }
});
for (const pre of document.querySelectorAll('pre')) {
  if (pre.closest('.diagram-source')) continue;
  const code = pre.querySelector('code');
  if (!code || !navigator.clipboard) continue;
  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'copy-code';
  button.textContent = 'Copy';
  button.setAttribute('aria-label', 'Copy code block');
  button.addEventListener('click', async () => {
    try { await navigator.clipboard.writeText(code.textContent); button.textContent = 'Copied'; }
    catch { button.textContent = 'Select to copy'; }
    setTimeout(() => { button.textContent = 'Copy'; }, 1800);
  });
  pre.append(button);
}
// Close only the mobile menu on first load; desktop keeps the full tree visible.
if (matchMedia('(max-width: 760px)').matches) document.querySelector('.mobile-nav')?.removeAttribute('open');
async function renderDiagrams() {
  const diagrams = [...document.querySelectorAll('.mermaid')];
  if (!diagrams.length) return;
  try {
    // Pinned local distribution: no runtime CDN dependency.
    const script = document.createElement('script');
    script.src = new URL('mermaid.min.js', document.currentScript?.src || [...document.scripts].find(s => s.src.endsWith('/site.js')).src).href;
    await new Promise((resolve, reject) => { script.onload = resolve; script.onerror = reject; document.head.append(script); });
    mermaid.initialize({startOnLoad: false, securityLevel: 'strict', theme: 'base', themeVariables: {
      primaryColor: '#e0f1f4', primaryTextColor: '#18273c', primaryBorderColor: '#006981', lineColor: '#52647b', fontFamily: 'system-ui', fontSize: '16px'
    }, flowchart: {htmlLabels: false}});
    for (const [index, element] of diagrams.entries()) {
      const source = element.textContent;
      try {
        const {svg} = await mermaid.render(`diagram-${index}`, source);
        element.innerHTML = svg;
        element.closest('figure').querySelector('details').removeAttribute('open');
      } catch { element.textContent = 'Diagram rendering unavailable. Read the diagram source below.'; }
    }
  } catch { /* Source remains visible, including offline or no-JS use. */ }
}
renderDiagrams();
