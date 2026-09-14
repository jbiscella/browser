// Probe: product/list card readability. Pass verbatim to browser_evaluate on a listing,
// search-results or home page. Finds cards heuristically (links containing a heading or
// a price), measures the visible part of each title with the card's real font, and
// counts titles whose visible text is identical to another card's.
() => {
  const priceRe = /(\d[\d.,\s]*\s?(€|CHF|£|\$|USD|EUR|zł|kr)|(€|CHF|£|\$)\s?\d)/;
  const anchors = [...document.querySelectorAll('a[href]')].filter(a => {
    const h = a.querySelector('h1,h2,h3,h4,[class*=title],[class*=heading],[class*=name]');
    const txt = a.innerText || '';
    return h && txt.length > 3 && (priceRe.test(txt) || priceRe.test(a.parentElement?.innerText || '') || /product|produit|prodott|item|artikel|\/p\//i.test(a.href));
  });
  // de-duplicate cards pointing at the same URL (carousel clones) but count them
  const seen = new Map(); anchors.forEach(a => seen.set(a.href, (seen.get(a.href) || 0) + 1));
  const uniq = []; const done = new Set(); anchors.forEach(a => { if (!done.has(a.href)) { done.add(a.href); uniq.push(a); } });
  const clones = anchors.length - uniq.length;
  const ctx = document.createElement('canvas').getContext('2d');
  const rows = uniq.map(a => {
    const h = a.querySelector('h1,h2,h3,h4,[class*=title],[class*=heading],[class*=name]');
    const cs = getComputedStyle(h);
    ctx.font = `${cs.fontWeight} ${cs.fontSize} ${cs.fontFamily}`;
    const full = h.textContent.trim().replace(/\s+/g, ' ');
    const lh = parseFloat(cs.lineHeight) || parseFloat(cs.fontSize) * 1.3;
    const clamp = cs.webkitLineClamp && cs.webkitLineClamp !== 'none' ? parseInt(cs.webkitLineClamp) : null;
    const nowrap = cs.whiteSpace === 'nowrap';
    const lines = nowrap ? 1 : (clamp || Math.max(1, Math.round(h.clientHeight / lh)));
    const budget = h.clientWidth * lines - (lines === 1 ? 12 : 0);
    let vis = full; while (vis.length && ctx.measureText(vis).width > budget) vis = vis.slice(0, -1);
    const truncated = vis.length < full.length && (nowrap || clamp || cs.overflow === 'hidden' || h.scrollHeight > h.clientHeight + 1);
    const priceEl = [...a.querySelectorAll('*')].find(e => e.children.length === 0 && priceRe.test(e.textContent));
    const pcs = priceEl ? getComputedStyle(priceEl) : null;
    const titleBefore = priceEl ? (h.compareDocumentPosition(priceEl) & Node.DOCUMENT_POSITION_FOLLOWING) !== 0 : null;
    const img = a.querySelector('img');
    return { full, vis: (truncated ? vis : full).trim(), truncated, lines, nowrap, clamp, titleW: h.clientWidth, titleFs: cs.fontSize, titleWeight: cs.fontWeight, titleColor: cs.color, priceFs: pcs?.fontSize || null, priceWeight: pcs?.fontWeight || null, titleBeforePrice: titleBefore, hasImg: !!img, imgPlaceholder: img ? /default|placeholder|no[-_]?image/i.test(img.currentSrc || img.src) : null, imgNatural: img ? img.naturalWidth : null, imgDisplayed: img ? Math.round(img.getBoundingClientRect().width) : null, titleAttr: !!(a.title || h.title), href: a.href };
  });
  const groups = {}; rows.forEach(r => { groups[r.vis] = (groups[r.vis] || 0) + 1; });
  const dup = Object.entries(groups).filter(([, n]) => n > 1).sort((a, b) => b[1] - a[1]);
  const first = uniq[0]; const perRow = first ? uniq.filter(x => Math.abs(x.getBoundingClientRect().top - first.getBoundingClientRect().top) < 5).length : 0;
  const avg = arr => arr.length ? Math.round(arr.reduce((s, v) => s + v, 0) / arr.length) : 0;
  return {
    url: location.href, viewport: innerWidth,
    cards: uniq.length, cloneCardsInDom: clones, cardsPerRow: perRow,
    truncated: rows.filter(r => r.truncated).length,
    indistinguishable: dup.reduce((s, [, n]) => s + n, 0),
    duplicateGroups: dup.slice(0, 8).map(([k, n]) => ({ visible: k, cards: n })),
    titleLenAvg: avg(rows.map(r => r.full.length)), visibleCharsAvg: avg(rows.map(r => r.vis.length)),
    titleWidthPx: rows[0]?.titleW || null, titleFontPx: rows[0]?.titleFs || null, titleWeight: rows[0]?.titleWeight || null,
    priceFontPx: rows[0]?.priceFs || null, priceWeight: rows[0]?.priceWeight || null,
    titleBeforePrice: rows[0]?.titleBeforePrice ?? null, titleTooltip: rows.some(r => r.titleAttr),
    nowrap: rows.filter(r => r.nowrap).length, lineClamp: rows[0]?.clamp || null,
    placeholders: rows.filter(r => r.imgPlaceholder).length, noImage: rows.filter(r => !r.hasImg).length,
    lowResImages: rows.filter(r => r.imgNatural && r.imgDisplayed && r.imgNatural < r.imgDisplayed).length,
    lowercaseTitles: rows.filter(r => /^[a-zà-ÿ]/.test(r.full)).map(r => r.full).slice(0, 10),
    soldOutCards: uniq.filter(a => /esaurit|épuisé|rupture|sold out|ausverkauft|out of stock|non disponibile|indisponible/i.test(a.innerText + ' ' + (a.parentElement?.innerText || ''))).length,
    sample: rows.slice(0, 6).map(r => ({ full: r.full, visible: r.vis, truncated: r.truncated }))
  };
}
