# Writing the report

The report is for the **site owner or their team**, in the language the lead gives you.
They know their shop, not UX vocabulary. They will read it on a phone as often as on a
laptop, and forward it to whoever maintains the site.

## Section order (fixed; headings translated)

1. **Header** — eyebrow "Usability audit", `h1` = bare host name, a 2–3 sentence lede
   that states the verdict (what works, what blocks), meta line with date, method,
   path tested.
2. **Verdict tiles** — three numbers: critical, important, positive findings.
3. **In brief** — one paragraph, then the measurement table (5–8 rows: the numbers that
   change what the reader does, each with a reference value).
4. **Critical findings** — each: chip + title, 1–2 paragraphs, a `fix` box, then the
   screenshot(s) that prove it, with a caption naming page and viewport.
5. **List readability** — always its own section, even when the result is positive:
   the truncation/indistinguishability table, one desktop and one mobile figure, causes,
   recommendations. Users ask for this specifically.
6. **Important findings** — same pattern, shorter; group screenshots in a `trio`.
7. **What works well** — bullet list of positives, one figure.
8. **Accessibility, minor points** — chips + one line each.
9. **Priorities** — numbered list ordered by effect / effort, each with a bold action,
   one sentence of detail and an `eff` line "Effort: … · Effect: …".
10. **Method** — date, viewports, tools, what was and was not done (e.g. "test order
    taken to the checkout form, no payment"); then the callout with every URL tested.
11. **Footer** — audit name, screenshot date, "prices and stock as shown that day".

## Writing rules

- Lead with the outcome; one idea per sentence; no jargon without a plain gloss the first
  time (LCP → "time until the main content appears").
- Every number in the text comes from `findings/*.json` or `capture/metrics.json`.
  Round sensibly (14.7 s, 64 MB, 96 of 100). Put numbers in tables when there are more
  than two in a row.
- Every product, page or query named gets the exact URL it was seen on, in the Method
  callout at least; critical findings also link inline.
- Fix boxes are imperative and concrete: name the theme setting, the CSS rule, the
  content to add. Give an effort estimate the owner can plan with.
- Never mention agents, phases, probes or this skill. The report reads as one author.
- Quote the site's own labels in the site's language inside guillemets or quotes; do not
  translate button labels.
- Positives are specific ("guest checkout with in-store pickup and PayPal"), not
  compliments.
- Do not pad. A section with nothing to say gets one sentence, not filler.

## Screenshots

- Pick 8–14 images. Each proves one claim; the caption says **page, viewport, what to
  look at** in bold + one clause.
- Crop to the evidence with `scripts/crop.py`: a card row, a form, the banner over the
  CTA. Full-page shots only for "the home is nine screens long" type claims, and then
  scaled to ≤ 700 px wide.
- Mobile captures go in `figure.phone` (max 300 px wide) or in a `trio`; desktop crops in
  `figure.wide`.
- Alt text describes what is visible, in the report language.
- Reference images as `{{IMG:filename.jpg}}`; `build_report.py` inlines them.

## HTML you produce: `WORK/report/body.html`

Only the content of the page: start with `<header>` and end with `<footer>`, inside one
`<div class="wrap">`. No `<html>`, `<head>`, `<style>`: the template provides them.
Use the classes defined in `templates/report-template.html`:

`eyebrow lede meta verdict n l chip crit imp min good finding fix tbl num figure wide
phone duo trio callout urls prio eff plus`

Set the title for `build_report.py --title` as `Audit <host>` and the language code as
`--lang`.

## Language notes

- Italian: «virgolette basse» for site labels; numbers `1 164`, `14,7 s`, `64 MB`.
- French: « guillemets avec espaces », `14,7 s`, `64 Mo`, `1 164`.
- German: „Anführungszeichen“, `14,7 s`, `64 MB`, `1 164`.
- English: "quotes", `14.7 s`, `64 MB`, `1,164`.
