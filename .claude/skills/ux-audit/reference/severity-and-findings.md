# Severity scale and findings schema

## Severity

| level | meaning | typical examples |
|---|---|---|
| `critical` | blocks or badly degrades the primary task for most visitors, on every visit | invisible add-to-cart, 60 MB home, banner covering the CTA on mobile, search returning unrelated results, > 20 % of list titles indistinguishable |
| `important` | costs conversions or trust for a meaningful share of visitors, or on key pages | product page without description, shipping cost hidden until checkout, no back-in-stock, wrong brand on half the catalogue, placeholders in legal pages |
| `minor` | polish, accessibility detail, consistency | 20 px carousel arrows, five images without alt, lowercase titles, focus ring default |
| `positive` | something that works well and must be kept | guest checkout, good filters, rich descriptions, fast load |

Rate by **impact × reach**, not by how easy the fix is. Effort goes in `effort`.

Rules:
- A finding without a measured number, a screenshot or a quoted text is not a finding.
- One finding = one problem. Do not bundle "product page is poor" with five sub-issues;
  split them or pick the worst.
- The same problem on many pages is one finding with `evidence.urls` listing them.
- Positives are findings too; the report needs them and the writer will not invent them.

## Findings file: `WORK/findings/<area>.json`

```json
{
  "area": "listing",
  "site": "https://example.com/",
  "generated": "2026-09-14T10:32:00Z",
  "summary": "Two or three sentences the lead can paste into the headlines digest.",
  "findings": [
    {
      "id": "listing-01",
      "severity": "critical",
      "title": "Card titles are truncated to one line and 96 of 100 are identical",
      "what": "Plain description of what the visitor experiences, 1–3 sentences.",
      "why": "Why it matters for this site's task, 1–2 sentences.",
      "evidence": {
        "urls": ["https://example.com/collections/x"],
        "measurements": {
          "cards": 100, "truncated": 100, "indistinguishable": 96,
          "title_width_px": 201, "visible_chars_avg": 24
        },
        "quotes": ["Age Of Sigmar Blades of…"],
        "screenshots": ["capture/screenshots/collection-desktop.jpeg"],
        "probe": "list-readability"
      },
      "fix": "Concrete, implementable recommendation. Name the setting, CSS rule or content change.",
      "effort": "hours | day | project",
      "viewport": "desktop | mobile | both",
      "heuristic": "heuristics.md §3 title truncation",
      "related_ids": [],
      "merged_into": null,
      "notes": ""
    }
  ],
  "requests": []
}
```

Field rules:
- `id`: `<area>-NN`, stable once written (the cross-check round references them).
- `evidence.measurements`: numbers only, with units in the key name when not obvious.
- `evidence.screenshots`: paths relative to `WORK`; only files that exist.
- `fix`: written for the site owner, not for a developer who knows the codebase; if it
  is a platform setting (Shopify theme editor, WooCommerce option), say where.
- `effort`: `hours` (same day), `day` (one working day), `project` (needs planning).
- `merged_into`: set to another finding's id when you concede a duplicate; the writer
  skips merged findings but keeps their evidence URLs under the surviving one.
- `requests` (optional, also mirrored to `WORK/requests/<area>.json`): array of
  `{ "kind": "screenshot|probe|page", "url": "...", "viewport": "mobile", "note": "..." }`
  — at most three per analyst, only for things the analyst cannot obtain with
  `fetch_page` or `curl`.

## Headlines digest: `WORK/findings/_headlines.md`

Built by the lead, one line per finding:

```
[listing] [critical] listing-01 — Card titles truncated, 96/100 identical — https://…/collections/x
```

Sorted critical → important → minor → positive, then by area. Analysts read this file in
the cross-check round; it is the only thing they see of each other's work, so the
`title` must carry the number.
