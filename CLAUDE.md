# CLAUDE.md

**Read [AGENTS.md](AGENTS.md) first** — it holds the design constraints and the traps
(bounded output, engine rot, what markitdown silently drops). This file only covers what
is specific to running inside Claude Code.

## Two MCP servers, registered in [.mcp.json](.mcp.json)

| server | use it for |
|---|---|
| `research` | *this repo.* Search, fetch, download, convert, page through big docs. |
| `playwright` | Microsoft's official Playwright MCP. Interactive browsing: click, type, **log into a site**. |

They're project-scoped, so Claude Code reads `.mcp.json` at startup and prompts once to
approve them. **A new server or a changed command needs a session restart** — `/mcp` shows
what's actually connected.

Tools appear as `mcp__research__web_search`, `mcp__research__to_markdown`, etc.

## Which tool to reach for

- **Start with `research(query)`** — it searches *and* fetches the top N in one call, and
  returns a bounded preview + `path` per source. It's the cheapest way into a topic.
- Then **`search_document(path, pattern)` → `read_document(path, offset)`** to go deep.
  Do **not** page a long document from offset 0; search for the section you want.
- `download(url)` returns a *path only*, never content. Follow with `to_markdown(path)`.
- `fetch_page(url)` works on a `.pdf` link too — it detects a non-HTML URL and
  downloads+converts instead of rendering.
- Reach for the **`playwright`** server only when a site needs a human-ish session
  (cookie wall, login, a form). It's token-hungry — don't use it for plain retrieval.

Prefer these over the built-in `WebSearch`/`WebFetch` when the job is *documents*: real
browser rendering, PDFs to disk, and conversion are the whole point of this repo. The
built-ins are fine for a quick factual lookup.

## Don't defeat the context guard

Tool output is truncated **on purpose** (~20k chars) with the full text on disk. When you
see `"truncated": true`:

- ❌ don't re-fetch, don't raise `limit`, don't `Read` the whole `.md` file
- ✅ `search_document(path, pattern)` → offsets → `read_document(path, offset)`

`Read`-ing a converted 300-page PDF directly from `documents/` bypasses every bound in the
system and is the one thing this repo is built to prevent.

## Verifying a change

Don't trust "it imports". This project talks to live sites and a live PDF parser:

```bash
make test        # offline: bounded-output invariant + SERP parser fixtures
make smoke       # live end-to-end: search -> download a PDF -> convert -> grep
make handshake   # spawn the server over stdio, list tools (catches a stray print())
```

`make smoke` is the one that matters after touching `engines.py`, `fetch.py`, or
`download.py` — the offline tests can pass while a real search returns nothing.

## Working with the user's documents

`documents/` holds real personal insurance policies and their conditions. They are private:
convert and read them locally, and **never publish them** — no Artifacts, no uploads, no
pasting contents into an external service.

When retrieving official conditions, **verify the edition inside the converted text against
what the policy cites**, and say so. A plausible-looking document of the wrong edition is
worse than none.

## Skills in this repo

`/ux-audit <url> [--lang it] [--out ~/dir]` runs a multi-agent usability audit of a live
site and writes `~/<host>-usability-report/report.html` plus a zip. It is defined in
[.claude/skills/ux-audit/SKILL.md](.claude/skills/ux-audit/SKILL.md) and uses the agents
in [.claude/agents/](.claude/agents/): `ux-recon` (map the site), `ux-capture` (the
**only** agent that may drive the shared Playwright browser), six `ux-analyst` in
parallel, and `ux-report-writer`. Heuristics, severity scale, probe scripts and the
report template live next to the skill; edit those, not the agents, to change what an
audit checks.

