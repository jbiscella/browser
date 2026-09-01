"""The bounded-output funnel.

Every tool that produces text returns through `emit()`. A converted 300-page PDF
is ~1M characters; returning that inline would blow the agent's context window in
a single call. So: the full text always goes to disk, and the caller gets a
bounded preview plus a path it can page into with `read_window` / `search_text`.

Offsets are character offsets, and `search_text` is a grep -- deliberately the
same shape as Claude Code's own Read/Grep, so the model already knows how to
drive them without being taught.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from webresearch.config import settings

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
_TRUNCATION_NOTE = (
    "Output truncated. The FULL text is saved at `path`. "
    "Use search_document(path, pattern) to jump straight to the relevant sections, "
    "then read_document(path, offset, limit) to page around a hit. "
    "Do NOT try to read a large document end-to-end."
)


def slugify(text: str, *, max_len: int = 60) -> str:
    """Filesystem-safe stem. Falls back to a hash when nothing survives."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = _SLUG_STRIP.sub("-", ascii_only).strip("-")[:max_len].strip("-")
    if not slug:
        slug = "doc-" + hashlib.sha1((text or "").encode("utf-8")).hexdigest()[:10]
    return slug


def _unique_path(stem: str, ext: str) -> Path:
    candidate = settings.docs_dir / f"{stem}{ext}"
    n = 1
    while candidate.exists():
        candidate = settings.docs_dir / f"{stem}-{n}{ext}"
        n += 1
    return candidate


def resolve_in_docs(name: str, ext: str = "") -> Path:
    """A safe, unique path inside docs_dir for a new file."""
    return _unique_path(slugify(name), ext)


def save_text(text: str, *, stem: str, ext: str = ".md") -> Path:
    path = _unique_path(slugify(stem), ext)
    path.write_text(text, encoding="utf-8")
    return path


def emit(
    text: str,
    *,
    stem: str,
    source: str | None = None,
    path: Path | None = None,
    warning: str | None = None,
) -> dict:
    """Persist `text` in full; return a payload bounded by max_inline_chars.

    Pass `path` when the text has already been written to disk (avoids a
    duplicate file), otherwise it is saved under a slug of `stem`.
    """
    if path is None:
        path = save_text(text, stem=stem)

    total = len(text)
    truncated = total > settings.max_inline_chars
    payload = {
        "path": str(path),
        "source": source,
        "total_chars": total,
        "approx_tokens": total // 4,
        "truncated": truncated,
        "content": text[: settings.max_inline_chars],
        "next_offset": settings.max_inline_chars if truncated else None,
    }
    if truncated:
        payload["note"] = _TRUNCATION_NOTE
    if warning:
        payload["warning"] = warning
    return payload


def _read(path: str | Path) -> tuple[Path, str]:
    p = Path(path).expanduser()
    if not p.is_absolute():
        p = settings.docs_dir / p
    if not p.is_file():
        raise FileNotFoundError(f"No such document: {p}")
    return p, p.read_text(encoding="utf-8", errors="replace")


def read_window(path: str | Path, offset: int = 0, limit: int | None = None) -> dict:
    """A clamped character window, snapped back to a line boundary."""
    p, text = _read(path)
    total = len(text)
    limit = min(limit or settings.max_inline_chars, settings.hard_max_chars)
    offset = max(0, min(offset, total))

    end = min(offset + limit, total)
    # Snap to the last newline so we don't hand back a half-sentence, unless
    # that would leave the window nearly empty.
    if end < total:
        nl = text.rfind("\n", offset, end)
        if nl > offset + limit // 2:
            end = nl + 1

    return {
        "path": str(p),
        "content": text[offset:end],
        "offset": offset,
        "next_offset": end if end < total else None,
        "total_chars": total,
        "eof": end >= total,
    }


def search_text(
    path: str | Path,
    pattern: str,
    *,
    context_chars: int = 300,
    max_matches: int = 20,
) -> dict:
    """Regex search returning offsets + excerpts -- the way into a large doc."""
    p, text = _read(path)
    try:
        rx = re.compile(pattern, re.IGNORECASE | re.MULTILINE)
    except re.error as exc:
        raise ValueError(f"Invalid regex {pattern!r}: {exc}") from exc

    matches: list[dict] = []
    budget = settings.max_inline_chars
    total_matches = 0

    for m in rx.finditer(text):
        total_matches += 1
        if len(matches) >= max_matches or budget <= 0:
            continue
        start = max(0, m.start() - context_chars)
        end = min(len(text), m.end() + context_chars)
        excerpt = text[start:end]
        budget -= len(excerpt)
        matches.append(
            {
                "offset": m.start(),
                "line_no": text.count("\n", 0, m.start()) + 1,
                "excerpt": excerpt,
            }
        )

    return {
        "path": str(p),
        "pattern": pattern,
        "total_matches": total_matches,
        "returned": len(matches),
        "truncated": total_matches > len(matches),
        "matches": matches,
    }


def list_documents() -> dict:
    files = []
    for f in sorted(settings.docs_dir.iterdir()):
        if f.is_file() and f.name != ".gitkeep":
            st = f.stat()
            files.append(
                {
                    "name": f.name,
                    "path": str(f),
                    "bytes": st.st_size,
                    "modified": datetime.fromtimestamp(
                        st.st_mtime, tz=timezone.utc
                    ).isoformat(timespec="seconds"),
                }
            )
    return {"dir": str(settings.docs_dir), "count": len(files), "files": files}
