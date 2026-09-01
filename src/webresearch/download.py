"""Stream a URL to documents/.

Two things that look like paranoia but aren't:
  - A browser User-Agent is mandatory. arxiv.org (and most CDN-fronted hosts)
    403 the default `python-httpx/x.y` UA.
  - On 403/429 we retry through Playwright's APIRequestContext, which inherits
    the real browser's TLS fingerprint and cookies. That rescues Cloudflare-
    fronted hosts that reject any bare HTTP client.
"""

from __future__ import annotations

import hashlib
import logging
import mimetypes
import re
from pathlib import Path
from urllib.parse import unquote, urlparse

import httpx

from webresearch.browser import manager
from webresearch.config import settings
from webresearch.store import resolve_in_docs

log = logging.getLogger(__name__)

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")

# Servers lie about Content-Type and markitdown dispatches on file extension,
# so sniff the actual bytes.
_MAGIC: list[tuple[bytes, str, str]] = [
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"PK\x03\x04", "application/zip", ".zip"),  # also docx/xlsx/pptx
    (b"\xd0\xcf\x11\xe0", "application/msword", ".doc"),
    (b"<!DOCTYPE", "text/html", ".html"),
    (b"<html", "text/html", ".html"),
]

_ZIP_OOXML = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
}


def _sniff(head: bytes, content_type: str) -> tuple[str, str | None]:
    for magic, mime, ext in _MAGIC:
        if head.startswith(magic):
            if mime == "application/zip":
                ext = _ZIP_OOXML.get(content_type.split(";")[0].strip(), ext)
                mime = content_type.split(";")[0].strip() or mime
            return mime, ext
    return content_type.split(";")[0].strip() or "application/octet-stream", None


def _pick_name(url: str, explicit: str | None, disposition: str | None) -> str:
    if explicit:
        return _UNSAFE.sub("_", Path(explicit).name)

    if disposition:
        m = re.search(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', disposition, re.I)
        if m:
            return _UNSAFE.sub("_", Path(unquote(m.group(1))).name)

    tail = Path(unquote(urlparse(url).path)).name
    if tail:
        return _UNSAFE.sub("_", tail)

    return "download-" + hashlib.sha1(url.encode()).hexdigest()[:12]


async def _via_browser(url: str) -> tuple[bytes, str]:
    async with manager.context(block_heavy=False) as ctx:
        resp = await ctx.request.get(url, timeout=60_000)
        if not resp.ok:
            raise RuntimeError(f"HTTP {resp.status} fetching {url} (browser retry)")
        return await resp.body(), (resp.headers.get("content-type") or "")


async def download(url: str, filename: str | None = None) -> dict:
    max_bytes = settings.max_download_mb * 1024 * 1024
    headers = {"User-Agent": settings.user_agent, "Accept": "*/*"}
    body: bytes | None = None
    content_type = ""
    disposition: str | None = None

    async with httpx.AsyncClient(
        follow_redirects=True, timeout=60.0, headers=headers
    ) as client:
        try:
            async with client.stream("GET", url) as resp:
                if resp.status_code in (403, 429):
                    raise PermissionError(f"HTTP {resp.status_code}")
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                disposition = resp.headers.get("content-disposition")

                chunks: list[bytes] = []
                size = 0
                async for chunk in resp.aiter_bytes(65_536):
                    size += len(chunk)
                    if size > max_bytes:
                        raise ValueError(
                            f"Download exceeds {settings.max_download_mb} MB limit: {url}"
                        )
                    chunks.append(chunk)
                body = b"".join(chunks)
        except PermissionError as exc:
            log.warning("%s on %s -- retrying through the browser", exc, url)
            body, content_type = await _via_browser(url)
            if len(body) > max_bytes:
                raise ValueError(
                    f"Download exceeds {settings.max_download_mb} MB limit: {url}"
                ) from exc

    assert body is not None
    detected_type, sniffed_ext = _sniff(body[:512], content_type)

    name = _pick_name(url, filename, disposition)
    stem, ext = (Path(name).stem, Path(name).suffix)
    if not ext:
        ext = sniffed_ext or mimetypes.guess_extension(detected_type) or ".bin"
    elif sniffed_ext and ext.lower() != sniffed_ext and sniffed_ext == ".pdf":
        # Content really is a PDF whatever the URL claimed.
        ext = ".pdf"

    path = resolve_in_docs(stem, ext)
    path.write_bytes(body)

    return {
        "path": str(path),
        "filename": path.name,
        "bytes": len(body),
        "content_type": content_type.split(";")[0].strip(),
        "detected_type": detected_type,
        "url": url,
    }
