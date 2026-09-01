"""End-to-end proof, driving the library directly (no MCP layer).

The last check is the important one: it asserts that no call ever returned more
than max_inline_chars of inline content. That is the failure mode this whole
project is built to avoid.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from webresearch import browser, search, store
from webresearch.config import settings
from webresearch.convert import convert_file
from webresearch.download import download
from webresearch.fetch import fetch_page

PDF_URL = "https://arxiv.org/pdf/1706.03762"
biggest = 0


def check(label: str, ok: bool, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {label}" + (f" -- {detail}" if detail else ""), file=sys.stderr)
    if not ok:
        raise SystemExit(1)


def track(payload: dict) -> dict:
    global biggest
    biggest = max(biggest, len(payload.get("content", "")))
    return payload


async def main() -> None:
    print("\n=== 1. web_search (real browser) ===", file=sys.stderr)
    found = await search.search("attention is all you need transformer paper", max_results=5)
    check("search returned >=3 results", len(found["results"]) >= 3,
          f"{found['count']} via {found['engine']}")
    for r in found["results"][:3]:
        print(f"    - {r['title'][:70]}\n      {r['url']}", file=sys.stderr)

    print("\n=== 2. download a PDF (arxiv 403s naive clients) ===", file=sys.stderr)
    info = await download(PDF_URL)
    check("got a PDF", info["detected_type"] == "application/pdf", info["detected_type"])
    check("PDF is >1MB", info["bytes"] > 1_000_000, f"{info['bytes']:,} bytes")
    print(f"    saved: {info['path']}", file=sys.stderr)

    print("\n=== 3. to_markdown (markitdown) ===", file=sys.stderr)
    pdf = Path(info["path"])
    md, warning = await convert_file(pdf)
    md_path = pdf.with_suffix(".md")
    md_path.write_text(md, encoding="utf-8")
    payload = track(store.emit(md, stem=pdf.stem, path=md_path))
    check("conversion is substantial", payload["total_chars"] > 20_000,
          f"{payload['total_chars']:,} chars")
    check("output was truncated (bounded)", payload["truncated"] is True)
    check("content looks like the paper", "attention is all you need" in md.lower())
    check("no scan warning", warning is None, str(warning))

    print("\n=== 4. search_document (the way into a big doc) ===", file=sys.stderr)
    hits = track(store.search_text(md_path, r"multi-head attention", max_matches=3))
    check("found matches", hits["total_matches"] > 0, f"{hits['total_matches']} hits")
    offset = hits["matches"][0]["offset"]
    print(f"    first hit at offset {offset} (line {hits['matches'][0]['line_no']})",
          file=sys.stderr)

    print("\n=== 5. read_document at that offset ===", file=sys.stderr)
    window = track(store.read_window(md_path, offset=offset, limit=400))
    check("window returned", len(window["content"]) > 0)
    print(f"    {window['content'][:200]!r}...", file=sys.stderr)

    print("\n=== 6. fetch_page (JS render) ===", file=sys.stderr)
    page = await fetch_page("https://example.com")
    track(store.emit(page["markdown"], stem="example"))
    check("rendered example.com", "example domain" in page["markdown"].lower())

    print("\n=== 7. THE INVARIANT ===", file=sys.stderr)
    ceiling = settings.max_inline_chars
    check(
        "no call returned more than max_inline_chars inline",
        biggest <= ceiling,
        f"largest inline payload {biggest:,} chars vs ceiling {ceiling:,}",
    )

    await browser.manager.close()
    print("\nALL CHECKS PASSED\n", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
