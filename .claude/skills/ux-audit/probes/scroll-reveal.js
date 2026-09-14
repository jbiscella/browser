// Probe: scroll the page to trigger lazy-loading and scroll-reveal animations, then
// return to top. Run BEFORE a full-page screenshot on themes that hide sections until
// scrolled (Shopify Dawn, AOS, WOW.js). Also reports section order and heights, which
// the content-trust analyst uses to judge whether the main task is reachable early.
async () => {
  const before = [...document.querySelectorAll('*')].filter(e => getComputedStyle(e).opacity === '0' && e.getBoundingClientRect().height > 40).length;
  const h = document.documentElement.scrollHeight;
  for (let y = 0; y < h; y += Math.round(innerHeight * 0.6)) { window.scrollTo(0, y); await new Promise(r => setTimeout(r, 120)); }
  await new Promise(r => setTimeout(r, 500));
  window.scrollTo(0, 0);
  await new Promise(r => setTimeout(r, 400));
  const after = [...document.querySelectorAll('*')].filter(e => getComputedStyle(e).opacity === '0' && e.getBoundingClientRect().height > 40).length;
  const sectionSel = 'main > section, main > div > section, .shopify-section, main > [class*=section], body > section, [data-section-type]';
  const sections = [...document.querySelectorAll(sectionSel)].filter(s => s.getBoundingClientRect().height > 40).map(s => { const r = s.getBoundingClientRect(); const hd = s.querySelector('h1,h2,h3'); return { id: (s.id || s.className || '').toString().slice(0, 50), top_px: Math.round(r.top + scrollY), height_px: Math.round(r.height), heading: hd?.innerText.trim().slice(0, 60) || null, productLinks: s.querySelectorAll('a[href*=product], a[href*=produit], a[href*=prodott], a[href*="/p/"]').length }; });
  const firstProducts = sections.find(s => s.productLinks >= 3);
  return { pageHeight: document.documentElement.scrollHeight, viewportHeight: innerHeight, screens: Math.round(document.documentElement.scrollHeight / innerHeight * 10) / 10, hiddenBeforeScroll: before, hiddenAfterScroll: after, sections: sections.slice(0, 25), firstProductSectionTop_px: firstProducts ? firstProducts.top_px : null };
}
