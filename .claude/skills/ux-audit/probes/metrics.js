// Probe: page-level metrics. Pass verbatim to mcp__playwright__browser_evaluate.
// Returns transfer size, LCP, CLS, resource breakdown, heaviest resources, image stats,
// heading outline, link/button naming gaps, cookie/consent presence, third-party hosts.
() => {
  const nav = performance.getEntriesByType('navigation')[0] || {};
  const res = performance.getEntriesByType('resource');
  const kb = n => Math.round(n / 1024);
  const byType = {};
  res.forEach(r => { const t = r.initiatorType || 'other'; byType[t] = byType[t] || { n: 0, kb: 0 }; byType[t].n++; byType[t].kb += kb(r.transferSize || 0); });
  const heaviest = res.slice().sort((a, b) => (b.transferSize || 0) - (a.transferSize || 0)).slice(0, 8)
    .map(r => ({ url: r.name.slice(0, 140), kb: kb(r.transferSize || 0), type: r.initiatorType }));
  const imgs = [...document.images];
  const withSize = imgs.filter(i => i.naturalWidth > 0 && i.getBoundingClientRect().width > 0);
  const oversized = withSize.filter(i => i.naturalWidth > i.getBoundingClientRect().width * 2).length;
  const noAlt = imgs.filter(i => !i.hasAttribute('alt')).length;
  const emptyAlt = imgs.filter(i => i.hasAttribute('alt') && !i.alt.trim()).length;
  const placeholders = imgs.filter(i => /default|placeholder|no[-_]?image|missing/i.test(i.currentSrc || i.src)).length;
  const hs = [...document.querySelectorAll('h1,h2,h3,h4')].map(h => h.tagName + ': ' + h.textContent.trim().replace(/\s+/g, ' ').slice(0, 70));
  const h1s = [...document.querySelectorAll('h1')].map(h => h.innerText.trim().slice(0, 80));
  const links = [...document.querySelectorAll('a')];
  const unnamedLinks = links.filter(a => !a.textContent.trim() && !a.getAttribute('aria-label') && !a.getAttribute('title') && !a.querySelector('img[alt]:not([alt=""]), svg[aria-label], [aria-label]')).length;
  const unnamedButtons = [...document.querySelectorAll('button')].filter(b => !b.textContent.trim() && !b.getAttribute('aria-label') && !b.getAttribute('title') && !b.querySelector('[aria-label], img[alt]:not([alt=""])')).length;
  const inputs = [...document.querySelectorAll('input:not([type=hidden]),select,textarea')];
  const unlabeled = inputs.filter(i => !(i.labels && i.labels.length) && !i.getAttribute('aria-label') && !i.getAttribute('aria-labelledby') && !i.placeholder).length;
  const skip = !!document.querySelector('a[href^="#"][class*=skip], a[href="#main"], a[href="#content"], a[href="#MainContent"]');
  const main = !!document.querySelector('main, [role=main]');
  const consentSel = '[class*=cookie],[id*=cookie],[class*=consent],[id*=consent],[class*=gdpr],[id*=gdpr],[id*=iubenda],[class*=iubenda],[id*=onetrust],[class*=cc-window],[id*=CybotCookiebot]';
  const consent = [...document.querySelectorAll(consentSel)].filter(e => { const r = e.getBoundingClientRect(); return r.width > 100 && r.height > 40 && getComputedStyle(e).visibility !== 'hidden'; })
    .map(e => { const r = e.getBoundingClientRect(); return { id: (e.id || e.className || '').toString().slice(0, 60), h: Math.round(r.height), w: Math.round(r.width), share: Math.round(r.height * r.width / (innerWidth * innerHeight) * 100), fixed: getComputedStyle(e).position === 'fixed', text: e.innerText.replace(/\s+/g, ' ').slice(0, 160) }; }).slice(0, 2);
  const hosts = [...new Set(res.map(r => { try { return new URL(r.name).host; } catch (e) { return ''; } }).filter(h => h && h !== location.host))];
  const cookies = document.cookie.split(';').map(c => c.trim().split('=')[0]).filter(Boolean);
  const fs = {}; [...document.querySelectorAll('p,li,a,span,td,label,button')].slice(0, 600).forEach(e => { const s = getComputedStyle(e).fontSize; fs[s] = (fs[s] || 0) + 1; });
  const small = Object.entries(fs).filter(([s]) => parseFloat(s) < 12).reduce((a, [, n]) => a + n, 0);
  const overflow = document.documentElement.scrollWidth > innerWidth + 1;
  const hidden = [...document.querySelectorAll('[class*=scroll-trigger],[class*=reveal],[data-aos],[class*=animate]')].filter(e => getComputedStyle(e).opacity === '0' && e.getBoundingClientRect().height > 40).length;
  const lcp = new Promise(r => { try { const o = new PerformanceObserver(l => { const e = l.getEntries().pop(); if (e) r(Math.round(e.startTime)); }); o.observe({ type: 'largest-contentful-paint', buffered: true }); setTimeout(() => r(null), 600); } catch (e) { r(null); } });
  const cls = new Promise(r => { try { let s = 0; const o = new PerformanceObserver(l => { l.getEntries().forEach(e => { if (!e.hadRecentInput) s += e.value; }); }); o.observe({ type: 'layout-shift', buffered: true }); setTimeout(() => r(Math.round(s * 1000) / 1000), 500); } catch (e) { r(null); } });
  return Promise.all([lcp, cls]).then(([l, c]) => ({
    url: location.href, title: document.title, lang: document.documentElement.lang || null,
    viewport: { w: innerWidth, h: innerHeight, scrollH: document.documentElement.scrollHeight, horizontalOverflow: overflow },
    timing: { domInteractive_ms: Math.round(nav.domInteractive || 0), load_ms: Math.round(nav.loadEventEnd || 0), lcp_ms: l, cls: c },
    transfer: { total_kb: kb(res.reduce((a, r) => a + (r.transferSize || 0), 0)), requests: res.length, byType, heaviest },
    images: { total: imgs.length, measured: withSize.length, oversized, noAlt, emptyAlt, placeholders, lazy: imgs.filter(i => i.loading === 'lazy').length },
    headings: { h1: h1s, outline: hs.slice(0, 40), h3_count: document.querySelectorAll('h3').length },
    naming: { links: links.length, unnamedLinks, unnamedButtons, inputs: inputs.length, unlabeledInputs: unlabeled, skipLink: skip, mainLandmark: main },
    text: { bodyFontPx: getComputedStyle(document.body).fontSize, fontSizes: fs, elementsUnder12px: small },
    consent, thirdPartyHosts: hosts.slice(0, 30), cookies,
    hiddenUntilScroll: hidden,
    meta: { description: document.querySelector('meta[name=description]')?.content || null, canonical: document.querySelector('link[rel=canonical]')?.href || null, hreflang: [...document.querySelectorAll('link[hreflang]')].map(l => l.hreflang), generator: document.querySelector('meta[name=generator]')?.content || null, jsonld: [...document.querySelectorAll('script[type="application/ld+json"]')].map(s => (s.textContent.match(/"@type"\s*:\s*"([^"]+)"/) || [])[1]).filter(Boolean) }
  }));
}
