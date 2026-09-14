// Probe: navigation and search surfaces. Pass verbatim to browser_evaluate on any page
// (home for the menu, a search-results page for results). Reports menu items with
// targets, external links without indication, search form, result count and first
// titles, sort and filter controls, pagination, and the "no results" exits.
() => {
  const t = document.body.innerText.replace(/\s+/g, ' ');
  const navLinks = [...document.querySelectorAll('header a[href], nav a[href], [role=navigation] a[href]')].filter(a => a.getBoundingClientRect().width > 0 || a.closest('details, [class*=drawer], [class*=menu]'));
  const items = []; const seen = new Set();
  navLinks.forEach(a => { const label = (a.innerText || a.getAttribute('aria-label') || '').trim().replace(/\s+/g, ' ').slice(0, 40); const key = label + '|' + a.href; if (!label || seen.has(key)) return; seen.add(key); let ext = false; try { ext = new URL(a.href).host !== location.host; } catch (e) { } items.push({ label, href: a.href.slice(0, 120), external: ext, newTab: a.target === '_blank', marked: ext && (/\b(extern|nouvelle fenêtre|new tab|nuova scheda)\b/i.test(a.getAttribute('aria-label') + ' ' + a.title) || !!a.querySelector('svg, [class*=external]')) }); });
  const topLevel = items.filter(i => !/login|account|accedi|connexion|cart|panier|carrello|warenkorb|search|cerca|recherche|suche/i.test(i.label)).slice(0, 25);
  const form = document.querySelector('form[action*=search], form[role=search], form:has(input[type=search]), form:has(input[name=q])');
  const input = form?.querySelector('input[type=search], input[name=q], input[name=s], input[type=text]');
  const searchVisible = input ? input.getBoundingClientRect().width > 0 : false;
  const searchIconOnly = !searchVisible && !!document.querySelector('[aria-label*=earch], [aria-label*=erca], [aria-label*=echerch], [class*=search] button, button[class*=search]');
  const countMatch = t.match(/(\d[\d.\s]*)\s*(risultat|résultat|result|ergebnis|articoli|articles|prodotti|produits|products|artikel)/i);
  const cardTitles = [...document.querySelectorAll('a[href] h2, a[href] h3, [class*=card] h3 a, [class*=product] h3 a, [class*=card__heading] a, [class*=product-title] a, h3 > a')].map(e => e.textContent.trim().replace(/\s+/g, ' ')).filter(Boolean);
  const uniqTitles = [...new Set(cardTitles)];
  const sort = [...document.querySelectorAll('select[name*=sort], select[id*=sort], select[class*=sort], [class*=sort] select')].map(s => [...s.options].map(o => o.text.trim()).slice(0, 12))[0] || null;
  const filters = [...document.querySelectorAll('[class*=facet] summary, [class*=filter] summary, [class*=facet] legend, [class*=filter] legend, [class*=filter-group] h3, [class*=facets__summary], aside [class*=filter] h3, aside details summary')].map(e => e.textContent.trim().replace(/\s+/g, ' ').slice(0, 30)).filter(Boolean);
  const filterButton = /\b(filtr|filter)\b/i.test([...document.querySelectorAll('button, summary, a')].map(b => b.innerText).join(' '));
  const pag = [...document.querySelectorAll('[class*=pagination] a, [class*=pagination] span, [class*=pagination] button, a[rel=next], a[rel=prev]')].map(e => e.textContent.trim()).filter(Boolean).slice(0, 12);
  const loadMore = /carica altri|load more|voir plus|mehr laden|mostra altri/i.test(t);
  const noResults = /nessun risultato|aucun résultat|no results|keine ergebnisse|0 risultat|0 résultat/i.test(t);
  const exits = noResults ? { links: [...(document.querySelector('main') || document.body).querySelectorAll('a[href]')].filter(a => !a.closest('header, footer, nav')).length, products: uniqTitles.length, suggestions: /suggerit|suggest|prova|essayez|try|popolari|populaires|popular|best/i.test(t) } : null;
  const bc = document.querySelector('nav[aria-label*=readcrumb i], .breadcrumb, .breadcrumbs, [class*=breadcrumb]');
  const langSwitch = !!document.querySelector('[class*=lang], [id*=lang], select[name*=locale], a[hreflang], [class*=locale]');
  return { url: location.href, viewport: innerWidth, menu: { topLevel, count: topLevel.length, external: topLevel.filter(i => i.external), unmarkedExternal: topLevel.filter(i => i.external && !i.marked && !i.newTab).length }, search: { formAction: form?.action || null, method: form?.method || null, inputVisible: searchVisible, iconOnly: searchIconOnly, placeholder: input?.placeholder || null, predictive: !!document.querySelector('predictive-search, [class*=predictive], [class*=autocomplete], [role=listbox]') }, results: { countText: countMatch ? countMatch[0] : null, count: countMatch ? parseInt(countMatch[1].replace(/[.\s]/g, '')) : null, cardsOnPage: uniqTitles.length, first: uniqTitles.slice(0, 6), sort, filters: [...new Set(filters)].slice(0, 12), filterButton, pagination: pag, loadMore, noResults, noResultsExits: exits }, breadcrumb: bc ? bc.innerText.replace(/\s+/g, ' ').slice(0, 120) : null, languageSwitcher: langSwitch, htmlLang: document.documentElement.lang || null };
}
