// Probe: product page completeness. Pass verbatim to browser_evaluate on a product page.
// Detects title, price, availability, CTA position, description length and structured
// attributes, images, shipping/pickup information, breadcrumb, related products, share,
// reviews, stock state and back-in-stock offer.
() => {
  const t = (document.querySelector('main') || document.body).innerText.replace(/\s+/g, ' ');
  const q = s => document.querySelector(s);
  const h1 = q('h1'); const priceRe = /(\d[\d.,\s]*\s?(€|CHF|£|\$|USD|EUR)|(€|CHF|£|\$)\s?\d[\d.,]*)/;
  const price = (t.match(priceRe) || [])[0] || null;
  const ctaSel = 'button[type=submit], [name=add], .product-form__submit, [class*=add-to-cart], [class*=addtocart], [class*=add_to_cart], button[class*=cart], form[action*=cart] button';
  const cta = [...document.querySelectorAll(ctaSel)].find(b => b.getBoundingClientRect().width > 0);
  const r = cta?.getBoundingClientRect();
  const descEl = q('[class*=description], [id*=description], .product__description, .rte, [itemprop=description], #tab-description');
  const desc = (descEl?.innerText || '').trim();
  const attrs = { players: /giocatori|joueurs|players|spieler/i.test(desc + t), age: /\b(età|âge|age|alter)\b|\d+\s?\+|\d+\s?(anni|ans|years|jahre)/i.test(desc), duration: /durata|durée|duration|minuti|minutes|min\b/i.test(desc), scale: /\b1[:\/]\d{2,3}\b|scala|échelle|scale/i.test(desc + (h1?.innerText || '')), dimensions: /\d+\s?(cm|mm)\b/i.test(desc), language: /lingua|langue|language|sprache|\((it|fr|en|de|eng)\)/i.test(desc + (h1?.innerText || '')), listItems: descEl ? descEl.querySelectorAll('li').length : 0, table: !!descEl?.querySelector('table, dl') };
  const imgs = [...document.querySelectorAll('main img, [class*=product] img, [class*=gallery] img')].filter(i => i.getBoundingClientRect().width > 80 && !/logo|icon|payment|badge/i.test(i.src + i.alt + i.className));
  const gallery = new Set(imgs.map(i => (i.currentSrc || i.src).split('?')[0])).size;
  const ship = t.match(/[^.]*?(spedizion|livraison|frais de port|shipping|versand|consegna|retrait|ritiro|pickup|abhol)[^.]*\./gi) || [];
  const stock = { available: /disponibil|in stock|en stock|verfügbar|articles? disponibles?|pronto/i.test(t), soldOut: /esaurit|épuisé|rupture|sold out|ausverkauft|out of stock|non disponibile|indisponible/i.test(t), qtyShown: (t.match(/(\d+)\s*(articoli|articles|pezzi|pièces|items|stück)\s*(disponibil|available|en stock)/i) || [])[1] || null, notify: /avvisami|notifica|prévenez|alert|notify|back in stock|benachrichtig|quando torna|disponibile di nuovo/i.test(t), preorder: /preordin|précommande|pre-order|preorder|vorbestell/i.test(t) };
  const trust = { reviews: /recension|review|avis|bewertung|stelle|étoiles|stars/i.test(t), payments: !!q('[class*=payment] img, [class*=payment-icons], [class*=trust]'), returns: /reso|retour|return|rückgabe|recesso|rembours/i.test(t), secure: /sicur|sécuris|secure|sicher/i.test(t) };
  const bc = q('nav[aria-label*=readcrumb i], .breadcrumb, .breadcrumbs, [class*=breadcrumb], ol[class*=crumb]');
  const bcClipped = bc ? bc.scrollWidth > bc.clientWidth + 2 : null;
  const related = document.querySelectorAll('[class*=related] a[href], [class*=recommend] a[href], product-recommendations a[href], [class*=upsell] a[href], [class*=cross] a[href]').length;
  const vendor = (q('[class*=vendor], [itemprop=brand], .product__text, [class*=brand]')?.innerText || '').trim().slice(0, 40) || null;
  const sku = (t.match(/\b(SKU|PLU|Ref\.?|Réf\.?|Codice|Art\.?-?Nr\.?)\s*:?\s*([\w-]+)/i) || [])[0] || null;
  const variants = document.querySelectorAll('select[name*=option], select[name*=variant], [class*=variant] input[type=radio], [class*=swatch]').length;
  const qty = !!q('input[type=number], input[name=quantity], [class*=quantity]');
  const expressBtn = [...document.querySelectorAll('[class*=payment-button], [class*=express], [class*=paypal] button, .shopify-payment-button__button, [aria-label*=PayPal], [class*=paypal-button]')].find(b => b.getBoundingClientRect().height > 20);
  const er = expressBtn?.getBoundingClientRect();
  return { url: location.href, title: h1?.innerText.trim().slice(0, 100) || null, price, vendor, sku, variants, quantitySelector: qty,
    cta: cta ? { text: cta.innerText.trim().slice(0, 40), disabled: cta.disabled, top_px: Math.round(r.top + scrollY), w: Math.round(r.width), h: Math.round(r.height), inFirstViewport: r.top + scrollY < innerHeight, bg: getComputedStyle(cta).backgroundColor, border: getComputedStyle(cta).borderTopWidth + ' ' + getComputedStyle(cta).borderTopColor } : null,
    expressPayment: expressBtn ? { text: (expressBtn.getAttribute('aria-label') || expressBtn.innerText || 'express').trim().slice(0, 30), top_px: Math.round(er.top + scrollY), h: Math.round(er.height), aboveCta: cta ? er.top < r.top : null } : null,
    description: { present: desc.length > 0, chars: desc.length, structured: attrs }, images: { count: imgs.length, uniqueSources: gallery, zoom: /zoom|ingrand|agrand/i.test(t) || !!q('[class*=zoom]') },
    shippingSentences: ship.slice(0, 4).map(s => s.trim().slice(0, 160)), pickupMentioned: /ritiro|retrait|pickup|abhol|click ?& ?collect/i.test(t), stock, trust,
    breadcrumb: { present: !!bc, clipped: bcClipped, text: bc?.innerText.replace(/\s+/g, ' ').slice(0, 100) || null }, relatedProducts: related, share: !!q('share-button, [class*=share]'), stickyCta: !!q('[class*=sticky][class*=cart], [class*=sticky-add]'),
    pageHeight: document.documentElement.scrollHeight, viewport: innerWidth };
}
