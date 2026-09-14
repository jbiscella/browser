# Heuristics and best practices the analysts test against

Each line is a check. An analyst reports a finding only when it can point at a page URL
and either a probe number, a screenshot, or a quoted text. "Feels slow" is not a finding;
"LCP 14.7 s on the home at 390 px, banner images 3.5–6.5 MB each" is.

Thresholds below are the ones used in the reports; cite them as the *reference* column.

## 1. Performance (area: performance)

| check | good | finding when |
|---|---|---|
| transfer size, home, cold | ≤ 2 MB | > 4 MB critical, > 2 MB important |
| LCP | ≤ 2.5 s | > 4 s critical, > 2.5 s important |
| CLS | ≤ 0.1 | > 0.25 critical, > 0.1 important |
| single image | ≤ 300 KB above the fold, ≤ 150 KB in cards | any image > 1 MB |
| oversized images | natural width ≤ 2× displayed width | > 25 % of images oversized |
| duplicated DOM (carousel clones) | none | products repeated ≥ 2× in DOM |
| console errors | 0 | any uncaught exception or 404 on every page |
| third-party hosts | known and consented | trackers firing before consent |
| scroll-reveal animation | content visible at rest | sections at `opacity:0` until scrolled |
| requests | ≤ 80 | > 150 |

Always name the heaviest 5 resources with their sizes.

## 2. Navigation and information architecture (area: navigation)

- Primary menu: ≤ 8 top-level items, labels are nouns the customer uses, no item leads
  off-site without an indication (icon, "opens new tab", or a different label).
- Every page reachable in ≤ 3 clicks from home; breadcrumbs on category and product
  pages; breadcrumb not clipped on mobile.
- Category pages: a description of what is inside, subcategories visible, item count.
- Search: box visible on every page (not only an icon on mobile if space allows);
  results page shows count, sort, **filters**, pagination; **relevance test** with three
  queries — a known product name, a two-word query, a misspelling — record count and
  first five titles; a query with **all** words must not return more than one with a
  single word (that means OR logic); "no results" page must offer categories, best
  sellers and a contact route, never only an error sentence.
- Locale: language matches the market; missing translations for a border/bilingual
  market are important; language switcher present if more than one.
- Dead ends: pages whose only exit is the footer; 404 page with a search or links.
- Consistency: same action, same label everywhere (Add to cart ≠ Buy ≠ Add).

## 3. Product lists and cards (area: listing)

This is the area users notice first and report as "I have to open everything".

- **Title truncation**: measure with `probes/list-readability.js`. Report the share of
  truncated titles and, more importantly, the share of titles whose *visible* text is
  identical to another card's on the same page ("indistinguishable"). > 20 %
  indistinguishable is critical; any truncation with a single-line `nowrap` rule is at
  least important.
- Titles should wrap to 2–3 lines; the distinctive part of the name must be visible;
  category prefixes that repeat the breadcrumb ("Age of Sigmar …" inside Age of Sigmar)
  should be stripped or demoted to a subtitle.
- Card content: image, name, price, and at least one deciding attribute for the category
  (players/age/duration for games; scale for models; size/colour for apparel; brand
  when the range is multi-brand). Name before price, or at least not visually dominated
  by it.
- Missing images: count placeholders; > 10 % is important, > 30 % critical.
- Image quality: natural width ≥ displayed width; consistent aspect ratio and background.
- Sold-out items: badge visible, and either sorted last, filterable, or hidden; "notify
  me" on the product page.
- Sort options include relevance, price both ways, newest; the default is sensible.
- Filters: at least type/category, price, availability, and the category's deciding
  attribute; filters present on search results too.
- Pagination or load-more with a visible position (page x of y); infinite scroll must
  keep the footer reachable.
- Badges: "Sale" only when compare-at price > price; "New" time-boxed; no badge covering
  the product.
- Hover/second image and quick-add are nice-to-have, not findings when absent.
- Title casing consistent (no random lowercase titles).

## 4. Product page and purchase flow (area: purchase)

- Above the fold on mobile: name, price, availability, primary CTA. The CTA must **look
  like a button**: filled background or visible border, contrast ≥ 3:1 against its
  surroundings, ≥ 44 px tall; it must not be visually weaker than an express-payment
  button (PayPal, Apple Pay, Shop Pay).
- Product information: description, key attributes as a list (not only prose), brand,
  reference/SKU, what is in the box, dimensions/scale/age where relevant, images ≥ 2.
- **Shipping disclosure**: cost or "free over X" and delivery time visible on the
  product page or at the latest in the cart, before the checkout; pickup option named.
- Add-to-cart feedback: drawer, modal or toast within 1 s, with a path to cart and a
  path to continue.
- Cart: editable quantities, remove, subtotal, shipping estimate or clear statement,
  persistent across pages.
- Checkout: guest checkout available; number of steps; fields marked required;
  address autocomplete; payment methods listed before the last step; pickup in store if
  the shop has one; no surprise costs.
- Sold-out: button disabled with a label, back-in-stock request, alternatives.
- Pre-orders labelled with a date.
- Error states: try an empty required field once on a contact form (never on payment).

## 5. Accessibility (area: accessibility)

WCAG 2.2 AA is the reference; report only what the probes or the snapshot show.

- One `h1` per page with visible text (a logo-only h1 is a minor finding); heading
  levels do not skip.
- Every `img` has `alt`; decorative ones have `alt=""`; icon links/buttons have a name.
- Form controls have labels; required state announced; errors linked to fields.
- Skip link present and first in tab order; focus visible on all interactive elements;
  no keyboard trap in menus, drawers, modals, carousels.
- Contrast: body text ≥ 4.5:1, large text and UI ≥ 3:1. Measure with
  `probes/contrast-and-targets.js`; verify against a screenshot, because gradient or
  image backgrounds fool the computed-style check.
- Tap targets ≥ 44×44 px for primary actions, ≥ 24×24 px for everything; ≥ 8 px apart.
- Base font ≥ 16 px on mobile; no more than a handful of elements < 12 px.
- No horizontal scroll at 390 px; content readable at 200 % zoom.
- `prefers-reduced-motion` respected; carousels pausable.
- Cookie/consent dialog: keyboard operable, does not trap focus forever, does not cover
  > 30 % of the mobile viewport, is not re-shown after a choice.
- Duplicated content for screen readers (visually hidden duplicates of titles, cloned
  carousel slides) is a minor finding unless it doubles every list.

## 6. Content, trust and legal (area: content-trust)

- Value proposition on the first screen: what is sold, to whom, where (for a local
  shop, the town); a slogan alone ("your creative space") is a finding.
- Section order on the home matches the business: the main catalogue before secondary
  services; the customer's main task reachable in the first two screens on mobile.
- Copy: consistent tone, no template leftovers, no placeholders (`[insert date]`), no
  raw English strings in a localised site, no duplicated blocks across pages that do not
  belong there.
- Vendor/brand data correct (shop's own name used as brand for third-party products is
  a finding); product titles consistent.
- Policies: shipping (cost, time, carriers, area), returns (window, conditions, who
  pays), legal notice (company, VAT/registration, address, contact), privacy; linked
  from footer and checkout; dates filled in.
- Contact: address that opens a map, `tel:`, `mailto:`, messaging link if advertised,
  opening hours on the contact page and footer, a form with required fields marked.
- Consent: a cookie banner where the law requires one (EU/UK/CH with analytics);
  trackers must not fire before consent; banner must be dismissable in one tap.
- Trust signals: reviews if any, payment logos, secure-checkout statement, physical
  store photos for local shops.
- SEO hygiene that affects users: `title` per page, meta description, canonical,
  hreflang when multilingual, structured data on products.

## 7. Visual design (all analysts note, `content-trust` collects)

- Hierarchy: one primary action per screen; primary and secondary buttons distinct.
- Typography: base 16–18 px, line length 45–80 characters, ≤ 3 sizes on a card.
- Spacing: consistent card heights in a row, no orphan card, no 700 px-tall card for a
  single item.
- Colour: accent used for actions only; semantic colours (error, success) separate.
- Imagery: consistent crop and background across cards; hero images sized to their box.
- Empty states designed (empty cart, no results, no reviews).
- Nothing important lives only in a hover state.

## 8. Mobile specifics

- Sticky header ≤ 15 % of viewport height; sticky cookie banner + sticky header + sticky
  add-to-cart must not together exceed 40 %.
- Menu drawer opens with the full catalogue reachable without scrolling past a banner.
- Filters open in a drawer with an apply button and a result count.
- Forms: correct input types (`email`, `tel`, numeric), autocomplete attributes.
- Product gallery swipeable with a position indicator.
