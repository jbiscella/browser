---
name: ux-audit
description: Multi-agent usability and web-design audit of a live website. Use when the user asks for a usability analysis, UX review, design critique, e-commerce audit, or a shareable report on a site. Spawns recon, capture, six analysts and a report writer; writes the report (HTML + screenshots + zip) into the user's home directory.
argument-hint: <url> [--lang it|fr|en|de] [--out ~/dir] [--focus listing,checkout,...]
user-invocable: true
allowed-tools:
  - Agent
  - SendMessage
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
  - mcp__research__fetch_page
  - mcp__research__web_search
  - mcp__playwright__browser_navigate
  - mcp__playwright__browser_resize
  - mcp__playwright__browser_evaluate
  - mcp__playwright__browser_take_screenshot
  - mcp__playwright__browser_snapshot
  - mcp__playwright__browser_click
  - mcp__playwright__browser_console_messages
  - mcp__playwright__browser_network_requests
---

# /ux-audit — multi-agent usability audit

You are the **lead**. You do not analyse the site yourself; you run the pipeline below,
carry information between agents, resolve disagreements, and hand the user a finished
report in their home directory. Everything an agent needs is passed **explicitly in its
prompt** (absolute paths, URL, language): subagents do not see this conversation.

## Arguments

`$ARGUMENTS` = `<url> [--lang xx] [--out dir] [--focus a,b]`

- `url` — required. Normalise to `https://` and keep the final URL after redirects.
- `--lang` — report language. Default: the language the user wrote their request in.
- `--out` — output directory. Default `~/<slug>-usability-report` where `slug` is the
  host without `www.` and TLD dots replaced by `-` (`minivers.ch` → `minivers-ch`).
- `--focus` — comma list of areas to weight more heavily (see area list). Never *skips*
  an area; it only tells analysts where to dig deeper.

## Hard constraints (read before spawning anything)

1. **One browser.** The `playwright` MCP server is a single shared Chrome. Only the
   `ux-capture` agent may use `mcp__playwright__*` tools, and only one instance of it may
   run at a time. Analysts work from captured files and the `research` server
   (`fetch_page`, separate headless browser, safe to use in parallel) plus `curl`.
   If capture fails with *"Browser is already in use"*, a stale Chrome from an earlier
   session holds the profile lock: `pkill -f ms-playwright-mcp/mcp-chrome` and retry once.
2. **Bounded output.** Never `Read` a whole converted page; agents write files and
   return short summaries. Findings live in JSON on disk, not in chat.
3. **Exact URLs, measured numbers.** Every claim in the report cites the page URL it was
   observed on and a number the probes produced. No guessed URLs, no invented metrics.
4. **Private by default.** The report goes to the user's home directory. Do not publish
   it anywhere unless the user asks.
5. **No purchases.** The purchase-flow analysis stops at the checkout form; never submit
   payment, never create accounts, never send contact forms.

## Workspace

```
WORK=<scratchpad>/ux-audit/<slug>          # pass this absolute path to every agent
WORK/site-map.json                          # recon output
WORK/capture/metrics.json                   # probe results per page × viewport
WORK/capture/screenshots/*.jpeg             # raw screenshots
WORK/capture/pages/*.md                     # fetch_page markdown per page
WORK/findings/<area>.json                   # one per analyst (schema in reference/)
WORK/findings/<area>.md                     # analyst's working notes (optional)
WORK/findings/_headlines.md                 # lead-built digest for the cross-check round
WORK/requests/<area>.json                   # extra captures an analyst asks for
WORK/report/body.html                       # writer output
<out>/                                      # final deliverable (home directory)
```

Create `WORK` and its subfolders with `mkdir -p` before phase 1.

## Pipeline

### Phase 0 — brief

Print one line to the user: URL, language, output directory, focus. Then proceed.

### Phase 1 — recon (foreground, no browser)

Spawn **`ux-recon`** with: the URL, `WORK`. Wait for it.
It writes `site-map.json`: platform, language(s), representative URLs for each page type
(home, one broad and one leaf category, in-stock product, sold-out product if any, search
with a hit and a miss, cart, checkout entry, contact, shipping/returns/legal pages),
sitemap counts, robots, headers, cookie/consent mechanism, third-party hosts.

If recon cannot find a category or product URL, it says so in `site-map.json.gaps`; you
still continue — capture will try the home links.

### Phase 2 — capture (foreground, the only browser user)

Spawn **`ux-capture`** with: `WORK`, and tell it to read `site-map.json`. Wait for it.
It runs every probe in `probes/` on each representative page at **1366×900** and
**390×844**, takes viewport and full-page screenshots, walks the purchase flow up to the
checkout form, and writes `capture/metrics.json` plus a `capture/INDEX.md` listing what
each screenshot shows. It dismisses cookie banners **after** capturing the page once with
the banner visible (the banner itself is a finding).

### Phase 3 — analysis (six analysts in parallel, background)

Spawn six **`ux-analyst`** agents **in one message**, each with `area`, `WORK`, the
report language, and the focus list. Areas and what each owns:

| area | owns |
|---|---|
| `performance` | weight, LCP, CLS, image sizing, request count, third parties, JS errors, scroll-reveal hiding content |
| `navigation` | IA, menu, labels, breadcrumbs, search behaviour (hit, miss, relevance, filters on results), language/locale, external links, dead ends |
| `listing` | product lists and cards: title truncation and distinguishability, information per card, sort/filter/pagination, sold-out handling, image quality, badge logic |
| `purchase` | product page completeness, add-to-cart visibility and feedback, cart, shipping-cost disclosure, checkout (guest, pickup, payment options), stock states |
| `accessibility` | headings, alt text, labels, focus, skip link, contrast, tap targets, font sizes, motion, keyboard traps, duplicated content for screen readers |
| `content-trust` | value proposition, copy quality, brand/vendor data, policies (shipping, returns, legal notice), contact page, cookie consent, placeholders and template leftovers |

Each analyst reads `site-map.json`, `capture/metrics.json`, `capture/INDEX.md` and the
`capture/pages/*.md` it needs (via `search_document`/`read_document`, never whole files),
may call `fetch_page`/`curl` for more pages, and writes `findings/<area>.json` following
`reference/severity-and-findings.md`. It may also write `requests/<area>.json` asking for
one extra capture (a page, a state, a crop) it cannot get without the browser.

Wait for all six. Then, if any `requests/*.json` exist, run **one** more `ux-capture`
pass with those requests (foreground), and tell the requesting analysts via
`SendMessage` where the new files are so they can finish.

### Phase 4 — cross-check round (agents talk through you)

1. Build `findings/_headlines.md`: for every finding in every JSON, one line
   `[area] [severity] id — title — evidence URL`. Sort by severity.
2. `SendMessage` each of the six analysts (same agents, context intact) with:
   *"Read `WORK/findings/_headlines.md`. (a) Which of your findings duplicate or overlap
   another area's? Point to the other id. (b) Where do you disagree with a severity?
   Say why in one line. (c) Which findings of others change how you would phrase yours?
   Update your `findings/<area>.json` accordingly (add `related_ids`, adjust `severity`,
   set `merged_into` on duplicates you concede) and reply with ≤10 lines of changes."*
3. Apply the tie-break rules: a duplicate lives in the area that owns the page type;
   severity disagreements resolve toward the analyst who has the measured number; when
   both have numbers, keep the higher severity and note the dissent in `notes`.
4. Re-read the JSONs. Reject any finding without `evidence.url` and a measurement or a
   screenshot; send it back to its analyst once, drop it if it comes back unchanged.

### Phase 5 — report (foreground)

Spawn **`ux-report-writer`** with: `WORK`, `<out>`, language, site name, audit date,
and the list of screenshots it may use. It:

- selects and crops screenshots with `scripts/crop.py` into `WORK/report/img/`;
- writes `WORK/report/body.html` following `reference/report-writing.md` and the
  section order in `templates/report-template.html`;
- runs `scripts/build_report.py` which inlines images, wraps the body in the template,
  writes `<out>/report.html`, copies `img/` and `findings/`, and produces `<out>.zip`.

### Phase 6 — verify and hand over

- `ls -la <out> <out>.zip`; open `<out>/report.html` with `Read` only on the first 60
  lines to confirm the title and language; confirm there are no `{{IMG:` placeholders
  left (`grep -c "{{IMG:" <out>/report.html` must print 0).
- Tell the user: output path, zip path, the three most severe findings with their
  measured numbers, and the count of findings per severity. Nothing else.

## Judgement calls the lead makes

- **Site is not a shop** (blog, SaaS, institution): keep all six analysts; `listing`
  audits whatever repeated-item lists exist (articles, plans, events) and `purchase`
  audits the primary conversion (sign-up, contact, download). Say so in the brief.
- **Site blocks automation** (captcha wall on every page): stop after recon, report what
  was observable from headers and `fetch_page`, and say plainly what could not be tested.
- **Login required for the core flow**: never create accounts. Audit up to the wall.
- **Time budget**: if an analyst has not returned after the capture of a comparable site
  would have finished twice over, message it once asking for what it has; use that.

## Files in this skill

- `reference/heuristics.md` — the checklists analysts test against (design, e-commerce,
  performance budgets, accessibility, mobile, content and trust).
- `reference/severity-and-findings.md` — severity scale and the findings JSON schema.
- `reference/report-writing.md` — how the report is written, in any language.
- `probes/*.js` — arrow functions for `browser_evaluate`; capture runs them verbatim.
- `scripts/crop.py`, `scripts/build_report.py` — image prep and report assembly.
- `templates/report-template.html` — CSS and skeleton the writer fills.
