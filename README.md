# browser — web research for AI agents

Search the web with a **real browser**, fetch JS-rendered pages, download PDFs, and convert
them to Markdown — **without flooding the agent's context window**.

Built because chat-based search can't retrieve and read real documents: it can't drive a
browser past a JS-heavy page, can't pull down a PDF, and can't read a 300-page document
without drowning in it.

## What it is

Two MCP servers, registered project-scoped in [.mcp.json](.mcp.json):

| server | for |
|---|---|
| **`research`** *(this repo)* | search, fetch, download, convert, and page through big documents |
| **`playwright`** | Microsoft's official [Playwright MCP](https://playwright.dev/mcp/introduction) — interactive browsing: click, type, log into a site |

Conversion uses Microsoft's [markitdown](https://github.com/microsoft/markitdown)
(PDF, docx, pptx, xlsx, html, …). Search prefers an official API (Tavily, free) and falls
back to driving a real headless Chromium via Playwright.

### Tools

| tool | returns |
|---|---|
| `research(query)` | **start here** — searches *and* fetches the top N; a bounded preview + `path` per source |
| `web_search(query, engine, max_results)` | `[{title, url, snippet}]` |
| `fetch_page(url)` | page → Markdown (JS-rendered; a `.pdf` link is downloaded + converted instead) |
| `download(url)` | file → `documents/`; returns a **path, never content** |
| `to_markdown(source)` | local path *or* URL → Markdown |
| `search_document(path, pattern)` | regex → offsets + excerpts — **the way into a large document** |
| `search_quota()` | remaining API allowance + the live source chain |
| `read_document(path, offset, limit)` | a character window |
| `render_page(path, page)` | PDF page → PNG, so the agent can **look** at diagrams/stat cards/symbols |
| `list_documents()` | what's been saved |

## Setup

```bash
make setup      # venv + deps + chromium
make test       # offline: bounded-output invariant + SERP parser fixtures
make smoke      # live end-to-end: search → download a PDF → convert → grep
make handshake  # spawn the server over stdio, list its tools
```

Requires Python 3.11+. The system pip is EXTERNALLY-MANAGED, so a venv is mandatory —
`make setup` handles it.

The Playwright MCP server needs Node ≥ 20. It lives in `~/.local/node-v22.13.0-linux-x64`,
symlinked into `~/.local/bin` — nothing was installed system-wide; delete those to remove it.

Claude Code reads `.mcp.json` at startup: **restart the session**, approve the two
project-scoped servers, then `/mcp` shows them connected.

## Usage

Just ask. The agent picks the tools:

> *"Find the SWICA COMPLETA TOP supplementary conditions, download the PDF, and tell me what
> it covers for dental treatment."*

Which becomes: `web_search` → `download` → `to_markdown` → `search_document("dentar")` →
`read_document(offset=…)` — with the full 24k-char document on disk and only the relevant
few hundred characters in context.

## The one design rule: no tool ever returns a whole document

A converted 300-page PDF is ~1M characters. Returning that inline blows the context window
in a single call, and preventing that is the point of this project.

Every text-producing tool funnels through `store.emit()`:

- the **full** text is written to `documents/`
- the caller gets a **bounded preview** (~20k chars) plus a `path`
- `search_document(path, pattern)` → offsets, then `read_document(path, offset)` → a window

You almost never want page 1 of a long document — you want the section about X. So search
for it. `tests/test_store.py` proves the cap holds against a synthetic 1M-char document.

Tune via env in `.mcp.json`: `WEBRESEARCH_DOCS_DIR`, `WEBRESEARCH_MAX_INLINE_CHARS`,
`WEBRESEARCH_MAX_DOWNLOAD_MB`, `WEBRESEARCH_HEADLESS`.

## Known limits

- **Images are dropped; there is no OCR.** markitdown's PDF path is text-layer only.
  Diagrams, stat cards, charts and symbol glyphs (e.g. Warhammer runemarks) do not survive.
  This is detected and reported in the `warning`, and **`render_page(path, n)` is the escape
  hatch**: it renders the page to a PNG so a vision-capable agent can simply *look* at it —
  which beats OCR, since OCR would inherit the same column-order problem and still lose the
  symbols.
- **Multi-column PDFs are handled** (`layout.py`). Naive extraction reads a 3-column page in
  y-then-x order and *braids* the columns — line 1 of col 1 + line 1 of col 2 + line 1 of
  col 3 become one line. It converts "successfully", with no warning, into text that still
  reads like prose and is nonsense. A recursive XY-cut recovers the real reading order, and
  the `warning` says when it kicked in.
- **Search engines rot.** Selectors break when an engine changes its markup. Everything
  breakage-prone is in one dict in [`engines.py`](src/webresearch/engines.py), backed by
  offline fixture tests. DuckDuckGo is currently **unusable** (403 on its HTML endpoints);
  Brave is primary, Bing secondary, Google a last resort.
- `documents/` is gitignored — downloads and conversions are never committed.

## Before you change anything

**Read [AGENTS.md](AGENTS.md).** It documents the non-obvious constraints and the traps
already paid for — why `is_blocked()` must read visible text rather than raw HTML, why the
HEAD pre-flight may only trust a 2xx, why a stray `print()` kills the server. Each looks
like a bug if you don't know why it's there.

Claude Code specifics are in [CLAUDE.md](CLAUDE.md).

## License

This project's code is **[0BSD](LICENSE)** — public-domain-equivalent. Use it for anything,
no attribution required.

Dependencies (direct and transitive) are listed in **[THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md)**
(`make licenses` regenerates it). All permissive — MIT / BSD / Apache-2.0 / PSF — with no
GPL, LGPL, AGPL or SSPL anywhere, so **no copyleft obligation attaches to this project**.
The only weak-copyleft component is `certifi` (MPL-2.0), whose file-level terms bind only
modifications to certifi's own files.

0BSD waives attribution *for this project's code*. Anyone redistributing a bundle that
vendors the dependencies must still preserve their copyright notices.

## Search sources — official APIs first, scraping as fallback

`engine="auto"` walks a chain, cleanest source first. `search_quota()` shows the live chain
and remaining allowance.

| # | source | key? | free tier | ToS-clean |
|---|---|---|---|---|
| 1 | **`tavily`** — official API | `TAVILY_API_KEY` | **1,000 credits/month**, no card | ✅ |
| 2 | `brave`, `bing`, `google` — **scraped** in a real Chromium | none | unlimited | ❌ **violates their ToS** |
| 3 | **`commoncrawl`** — open archive URL index | none | unlimited | ✅ |

**Get a key:** [tavily.com](https://tavily.com) → sign up → copy the `tvly-…` key into `.env`
(see [`.env.example`](.env.example)). One key, no cloud console, no project, no card.

With **no key set** the chain degrades to scraping — which works, and is what this repo did
originally, but is the part with legal exposure. Set `TAVILY_API_KEY` and the ToS-clean path
is used first, automatically.

**Keys live in a gitignored `.env`, never in `.mcp.json`** — that file is committed.

**Common Crawl is the free, keyless, always-legal last resort** — but be clear about what it
is: an index of **URLs, not page text**. It answers *"every PDF archived under swica.ch"*,
not *"what is a transformer"*, and it refuses a general query rather than guessing. Its
coverage is a **sample of the web, not a mirror**: measured against swica.ch, `hospita` and
`supplementa` return 60+ archived URLs while `infortuna` returns **zero** — that PDF has
simply never been crawled. A miss means *"not archived"*, never *"does not exist"*.

## Legal & operational risks

The dependency licenses are clean. The real exposure is elsewhere:

- **Scraping search engines violates their Terms of Service** (step 2 above). Contract/ToS,
  not copyright; enforcement against low-volume personal use is rare, but the risk isn't
  zero and no license here removes it. **Set `TAVILY_API_KEY` and the chain avoids it
  entirely.**

  There is no free, *keyless*, legal, general-purpose web-search API left in 2026. The
  landscape collapsed fast, so don't trust an older tutorial:

  | | status |
  |---|---|
  | Bing Web Search API | **retired** 11 Aug 2025 (Azure replacement: $35/1k) |
  | Brave Search API | free tier **killed** Feb 2026 → $5/1k |
  | Mojeek | paid |
  | Marginalia public JSON API | down (times out) |
  | SearXNG | just scrapes Google/Bing underneath — moves the problem, doesn't solve it |
  | **Tavily** | ✅ free 1k/month, no card — **the survivor** |
  | **Common Crawl** | ✅ free, keyless — but a URL index, not text search |
- **`robots.txt` is not consulted.** Neither for search pages nor for fetched pages. If you
  point this at a third-party site at volume, you are ignoring its stated crawl policy. Add
  a check, rate-limit, and identify yourself if you do anything beyond occasional retrieval.
- **The toolkit presents as a normal browser, not as a bot — and treats blocks as friction.**
  Pages render in a real Chromium, downloads send a browser User-Agent (the default
  `python-httpx/x.y` gets 403'd almost everywhere), and on a 403/429 `download.py` retries
  through the browser's own request stack, inheriting its cookies and TLS fingerprint.
  That is why it works, and it is also a choice with legal weight: a site that tries to
  refuse automated access is being routed around, not obeyed. For occasional retrieval of
  public pages this is the same exposure as the ToS point above; doing it at volume, or
  against a site that has clearly told you no, is a different conversation. When a site
  keeps blocking you, treat that as its answer.
- **Automating a logged-in account** (the interactive `playwright` server: cookie walls,
  logins, forms) falls under that account's own terms, and most sites prohibit automated
  access to authenticated areas. Occasional personal use of your own account is where the
  risk is lowest; anything systematic — scraping while logged in, bulk actions, resale of
  data behind a login — is squarely on you.
- **Downloaded documents remain copyrighted.** Fetching a public PDF and converting it for
  personal reading is ordinary use; republishing the converted Markdown generally is not.
  `documents/` is gitignored precisely so conversions don't get committed by accident.
- **`documents/` may contain personal data.** Converted policies and statements can hold
  names, addresses, dates of birth and national ID numbers, in plaintext, unencrypted. Do
  not commit that directory, sync it, or paste its contents into an external service —
  pasting into a chat or an artifact *is* a transfer. Data-protection law (GDPR, the Swiss
  FADP) applies to what you do with other people's data downstream of this tool; the tool
  does nothing to help you comply.
- **No warranty, no responsibility for misuse.** The code is [0BSD](LICENSE): provided
  as-is, and nothing in this section is legal advice. This is a general-purpose retrieval
  tool published for **lawful use** — personal research, reading documents you are entitled
  to read, retrieval a site permits. The author accepts **no responsibility for how you use
  it**: complying with a site's terms, robots policy, rate expectations, copyright and
  data-protection law is entirely the responsibility of the person running the tool. If a
  use is not licit, it is yours, not the author's.
