"""Environment-driven settings. Instantiated once at import."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Search API keys live in a gitignored .env, never in .mcp.json (which is
# committed). override=False so a real environment variable still wins.
load_dotenv(_PROJECT_ROOT / ".env", override=False)

# A realistic desktop Chrome UA. Used for both Playwright contexts and httpx
# downloads -- arxiv.org and most CDN-fronted hosts 403 the default httpx UA.
_DEFAULT_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ[name])
    except (KeyError, ValueError):
        return default


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    docs_dir: Path
    headless: bool
    #  No tool may return more inline content than this. The whole design hangs
    #  off it: full text goes to disk, a bounded window comes back.
    max_inline_chars: int
    #  Ceiling on a single explicit read_document window.
    hard_max_chars: int
    max_download_mb: int
    nav_timeout_ms: int
    browser_idle_secs: int
    convert_timeout_secs: int
    user_agent: str

    @classmethod
    def from_env(cls) -> "Settings":
        docs = Path(
            os.environ.get("WEBRESEARCH_DOCS_DIR", str(_PROJECT_ROOT / "documents"))
        ).expanduser().resolve()
        docs.mkdir(parents=True, exist_ok=True)
        return cls(
            docs_dir=docs,
            headless=_env_bool("WEBRESEARCH_HEADLESS", True),
            max_inline_chars=_env_int("WEBRESEARCH_MAX_INLINE_CHARS", 20_000),
            hard_max_chars=_env_int("WEBRESEARCH_HARD_MAX_CHARS", 100_000),
            max_download_mb=_env_int("WEBRESEARCH_MAX_DOWNLOAD_MB", 100),
            nav_timeout_ms=_env_int("WEBRESEARCH_NAV_TIMEOUT_MS", 30_000),
            browser_idle_secs=_env_int("WEBRESEARCH_BROWSER_IDLE_SECS", 300),
            convert_timeout_secs=_env_int("WEBRESEARCH_CONVERT_TIMEOUT_SECS", 180),
            user_agent=os.environ.get("WEBRESEARCH_USER_AGENT", _DEFAULT_UA),
        )


settings = Settings.from_env()
