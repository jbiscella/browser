# Working in this repo

A web-research toolkit exposed over MCP: search with a real browser, fetch JS-rendered
pages, download PDFs, convert them to Markdown with `markitdown`. Built because
chat-based search couldn't retrieve and read real documents.

Read this before changing `engines.py`, `store.py`, or `server.py` — each has a
non-obvious constraint that looks like a bug if you don't know why it's there.

## The one rule: never return a whole document

A converted 300-page PDF is ~1M characters. Returning that inline blows the context
window in one tool call, and that is the failure this project exists to prevent.

Every text-producing tool funnels through `store.emit()` (`src/webresearch/store.py`):

- full text → written to `documents/`
- caller gets → a bounded preview (`WEBRESEARCH_MAX_INLINE_CHARS`, default 20k) + a `path`
- to go deeper → `search_document(path, pattern)` for offsets, then `read_document(path, offset)`

**If you add a tool that returns text, route it through `emit()`.** Don't add a tool that
returns raw file content. `tests/test_store.py` pins the cap against a synthetic 1M-char
document; if it fails, the guard is gone.

To read a long document: search for what you need, don't page from the start. You almost
never want page 1 — you want the section about X.

## Search engines rot. Verify, don't assume.

`engines.py` holds every breakage-prone selector in one dict. It is the file that goes
stale. When `web_search` returns nothing, an engine changed its markup — re-capture a
fixture into `tests/fixtures/`, fix the dict, and let `tests/test_parsers.py` tell you
whether the fix is real.

Current state (verified 2026-07 — **re-verify before trusting**):

- **brave** — primary. Direct hrefs, stable markup, survives repeated hits.
- **bing** — secondary. Wraps *every* organic result in `bing.com/ck/a?…&u=a1<base64url>`;
  the real URL must be base64-decoded. Degrades to a JS shell with zero results when hit
  repeatedly from one IP.
- **google** — last resort. Bot-walls a headless browser almost immediately.
- **duckduckgo** — **dropped.** `html.duckduckgo.com/html/` and `/lite/` return **403**;
  the SPA renders nothing headless. Most DDG-scraper recipes online are dead. Don't
  reinstate it without confirming a real request returns real results.

## Search APIs: the landscape collapsed in 2025-26

Before recommending any search API, know that most of the obvious ones are dead:

- **Google Custom Search JSON API** — **closed to new customers**; API off 2027-01-01. A new
  project gets a permanent 403 that no amount of enabling or key-fixing resolves. Removed
  from this repo. **Do not add it back.**
- **Bing Web Search API** — retired 11 Aug 2025.
- **Brave Search API** — free tier killed Feb 2026 (ironic: `brave` is our primary scraper).
- **Mojeek** paid; **Marginalia**'s public JSON API is down; **SearXNG** scrapes Google
  underneath, so it relocates the ToS problem rather than removing it.
- **Tavily** — the surviving free option. 1000 credits/month, one key, no card. Recommend this.
- **Common Crawl** — free and keyless, but a URL index, not text search. Last in the chain.

## Traps already paid for (all pinned by tests)

- **`is_blocked()` matches visible text, not raw HTML.** A *healthy* Brave results page
  ships an i18n JS dictionary containing the word "captcha". Grepping raw markup flags
  every good page as blocked.
- **The HEAD pre-flight trusts `Content-Type` only on a 2xx.** Some CDNs answer HEAD with
  `400 + text/html` while GET returns the PDF fine (SWICA's does). Trusting that response
  makes `fetch_page` try to *render* a PDF as a web page.
- **Downloads need a browser User-Agent.** arxiv and most CDN-fronted hosts 403 the default
  `python-httpx/x.y`. On 403/429, `download.py` retries via Playwright's `APIRequestContext`,
  which inherits the browser's TLS fingerprint and cookies.
- **stdout is the JSON-RPC transport.** A single `print()` in the server corrupts the stream
  and it dies with an opaque parse error. Log to stderr. `make handshake` catches it.
- **markitdown runs in a thread** (`asyncio.to_thread`). pdfminer is synchronous and
  CPU-bound; a big PDF blocks 10–60 s and would freeze the whole event loop.

## PDFs: two silent corruptions, both now handled

markitdown's PDF path is pdfminer.six — **text layer only, single-column reading order**.
Both failures below produce output that *looks* fine, with no error. That is what makes them
dangerous: plausible, confident garbage is worse than a crash.

**1. Column braiding (`layout.py`).** pdfminer reads a page roughly y-then-x, so on a
3-column page it interleaves line 1 of col 1 + line 1 of col 2 + line 1 of col 3 into ONE
line. Three unrelated rules braided together, still reading like prose. Fixed with a
recursive XY-cut. Two things had to be right, and both are pinned by `tests/test_layout.py`:

- **Split into horizontal bands first.** A page is a *stack of regions* — full-width heading,
  then 3 columns, then a 2-column sidebar — not N columns top to bottom.
- **Ignore column-spanning words when finding gutters.** One full-width heading
  ("DISENGAGE ACTIONS") bridges every gutter and collapses the page to a single column.

Use pdfplumber (MIT) for coordinates. **Not PyMuPDF** — it has the best column detection
going, and it is AGPL; this project is 0BSD with no copyleft dependencies.

**2. Dropped images and glyphs.** Diagrams, stat cards, charts and symbol glyphs vanish with
no placeholder. There is **no OCR**, and OCR would not help anyway — it inherits the same
column problem and still loses symbols. `convert.py` counts what was lost and says so in the
`warning`; **`render_page(path, n)` renders the page to PNG so a vision model can just look
at it.** That is the escape hatch for anything text cannot reach.

Worked example: Warcry's rules say *"Fighters with the **Hero** runemark (⚙)…"* — the glyph
is an icon font, so the text layer yields `runemark ()`, empty parens. Rendering page 4 shows
the actual symbol. A fully scanned/image-only PDF is also detected and warned about.

## HTML: hidden elements survive conversion

`fetch_page`/`to_markdown` read the HTML, not the rendered CSS, so anything hidden with
`display:none` comes through as ordinary text. The PDF section above is about what
conversion silently *drops*; this is the opposite failure — text that was never visible —
and it's easier to act on by mistake, because a phantom reads as a positive confirmation.

Worked example (Aug 2026, Manning): a converted product page contained "you own this
product", which looked like proof of an entitlement. In a live browser it was
`<a class="ownership-indicator" style="display:none">` — a template element served to every
visitor, owner or not. The real state was "add to cart".

Treat converted markdown as evidence about **content**, never about **status** (owned /
logged-in / in-stock / enabled). To check status, use the interactive `playwright` server
and read `innerText` (which respects CSS) or `getComputedStyle(el).display` — and prefer
the body's state classes when the site exposes them (Manning: `user-logged-in`,
`user-doesnt-own-book`).

## Researching a product recommendation (or any "what's the best X for me" question)

A recommendation is only as good as the field it was drawn from. The failure to avoid is
**anchoring**: latching onto the first plausible brand/product and then only researching
*that*, so the "answer" was never actually compared against the alternatives. (Worked
example from this repo's history: recommending a Helinox table because it matched a Helinox
chair — same-brand bias — instead of discovering the field first. Casting wide later
confirmed Helinox *on merit* against 20 tested competitors AND surfaced a real alternative,
the NEMO Moonlander, that anchoring would never have shown.)

There is a **second** anchoring trap: defaulting to the obvious *entry-level* product instead
of first analysing the domain's **methodologies and quality bar**. (Worked example: asked for
the best miniature primer, answering "Chaos Black" — the beginner default — skips the painting
*method* the user is really choosing between: zenithal, slapchop, Contrast/speedpaint, airbrush
layering. Each implies a different primer colour and application type. The method reframes the
whole field, so it must be understood *before* products — hence Phase 1 below.)

Work the checklist top to bottom. Don't skip a phase; don't recommend before the last box.

**Phase 0 — Frame**
- [ ] Write down the user's **hard constraints** as explicit filters (e.g. `≥120 kg`,
      `packs < 40 cm`, `< 1.5 kg`, `sold in CH`) and their **soft preferences** separately.
- [ ] Note the deal-breakers that will decide the field (here: weight rating + packability).

**Phase 1 — Understand the domain: methodologies & quality (BEFORE any product)**
- [ ] Map the **methods / workflows / techniques** the user's goal implies. The best *product*
      is downstream of the *method* — pick the method first, then the product that serves it.
- [ ] Define what **"quality" means in this domain**: the axes experts actually judge on, and
      the quality/price tiers. Search `<category> techniques explained`, `how to choose
      <category>`, `<category> quality guide` — read a technique guide, not a product list.
- [ ] Decide which method + quality tier *this user* is in. If it's unclear and it would
      **change the answer**, ask 1–2 clarifying questions now (application type, technique,
      quality bar) rather than defaulting.
- [ ] ❌ Do NOT default to the obvious/entry-level product. That is a second anchoring trap:
      answering "black primer" skips the methodology (zenithal, slapchop, Contrast/speedpaint,
      airbrush layering) that decides whether black, grey, white, bone or coloured primer — and
      spray vs airbrush vs brush-on — is actually "best". The method reframes the whole field.

**Phase 2 — Discover the field (broad, generic, no brand yet)**
- [ ] Run **≥3 differently-worded** searches: `best <category> <constraint> tested reviewed`,
      `best <category> for <use case>`, `<category> comparison top picks`.
- [ ] **Craft the keywords deliberately, and rotate synonyms the moment a query underperforms.**
      The first phrasing that comes to mind is usually the weakest hit — reach for the field's own
      jargon and, for anything region-specific, the **local language of the market**. Generic or
      off-topic results are the signal to *re-word* (swap in a synonym, a native-language term, a
      technical name), never to mine the noise or give up. Worked examples (this repo's history):
      `bicycle import Switzerland customs` returned US shops until reworded to German `Einfuhr Velo
      Schweiz Zoll`; a Dutch bike's "cross frame" found nothing until searched as its real name
      `kruisframe`; retailer prices/specs surfaced under `verzendkosten`, `prijs`, `framemaat`, not
      their English equivalents. Keep 2–3 synonym sets per load-bearing term and rotate them.
- [ ] Ignore listicle spam; identify the **independent testers who buy & measure**
      (outdoorgearlab, cleverhiker, treelinereview, wirecutter, or the category's equivalent).
- [ ] `fetch_page` the **2–3 best roundups** and read their comparison tables — the candidate
      set lives there, not in snippets.
- [ ] ❌ Do NOT search a specific product/brand yet. Naming one now is the anchoring trap.

**Phase 3 — Build the candidate list, filter one by one**
- [ ] Extract **every** contender from the roundups into a list.
- [ ] Check each against the Phase-0 hard filters; mark pass/fail.
- [ ] Drop failures — but **name them and why**, don't delete silently (the user may flex a
      constraint). Keep near-misses visible.
- [ ] You should now have a **shortlist of 2–5** survivors.

**Phase 4 — Verify each survivor's specs at the source**
- [ ] For each shortlisted item, confirm the load-bearing numbers (capacity, packed size,
      weight, price, **local availability**) on a retailer/manufacturer page.
- [ ] Mark every figure as **page-confirmed** vs **snippet-only**; report that honestly.
- [ ] Expect blocks — see the fetch-reality note below.

**Phase 5 — Read reviews of the shortlist (reality vs the spec sheet)**
- [ ] Pull an **independent hands-on review** for each finalist.
- [ ] Hunt specifically for where lived experience **contradicts** the numbers (spec: "145 kg";
      review: "51 cm seat is tight for big users, slouches after 30 min" → flips the pick).
- [ ] A rating you can't corroborate in a real review is a **claim, not a finding** — say so.

**Phase 6 — Recommend**
- [ ] Present the **field you chose from**, not just the winner (otherwise it reads as a lookup).
- [ ] Tie the pick back to the user's specific constraints; give the runner-up and when to prefer it.
- [ ] State residual gaps (snippet-only prices, pages you couldn't open).

Scale to stakes: a quick factual pick may need only Phase 2 + one roundup; "help me buy X"
earns the whole list — and anything with real technique behind it (hobby gear, tools,
instruments) earns Phase 1 first, or you'll recommend the beginner default. Two realities the phases lean on:
- **Prefer `tavily` (official API) and stay legal** — see the search-chain notes above. A
  broad sweep is many queries; fine, the free tier is 1000/month.
- **Commercial pages fight the scraper.** Galaxus returns `ERR_HTTP2_PROTOCOL_ERROR`, retail
  sites bury content under cookie walls, some serve a "checking your browser" JS challenge.
  Expect a real full-page fetch hit rate around **1-in-2** on shopping sites. When a page
  blocks the headless fetch, fall back to the interactive **`playwright`** MCP server — that
  is exactly what it is for.

## Finding official documents online

Publishers don't expose a clean index. Two worked patterns from this repo's history:

- **SWICA**: `www4.swica.ch/p/<NNN>_<lang>_<NAME>.pdf`, where `<lang>` is `i`/`f`/`d`/`e`.
  Same document number across languages. Guessable once you have one.
- **AXA**: `axa.ch/doc/<code>` where the code is **language-specific with no pattern**
  (`ag593` = EN, `ag6be` = IT — same document). Sibling/sequential codes do not exist.
  Italian codes appear only on Italian product pages, behind
  `/servlets/external/docstoredocument?accesscode=<code>` — a plain `/doc/` scrape misses
  them, and search engines never surface them.

**Always verify the edition inside the converted document**, not from the filename or link.
A "latest version" short-link can drift away from the edition a contract is bound to, and
the most obvious search hit is often a superseded edition (SWICA `015` is the 2023 CGA;
the 2024 one a policy actually cites is a different document number, `030`).

## Conventions

- Python 3.11, `.venv` (system pip is EXTERNALLY-MANAGED — a venv is mandatory).
- `make setup` / `make test` / `make smoke` / `make handshake`.
- `documents/` is gitignored. Downloads and conversions are not committed.
- Tests must not touch the real `documents/` dir — `tests/conftest.py` redirects it to a
  tempdir, and it must be imported before any `webresearch` module (settings read env at
  import time).
- Tool docstrings in `server.py` are the MCP tool descriptions the model reads. They are
  the only thing steering it away from asking for a million characters. Treat them as code.
