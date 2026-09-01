"""One long-lived Chromium, a fresh BrowserContext per call.

Lazy launch matters: Claude Code starts every configured MCP server at session
boot, so an eager launch would leave ~300MB of Chromium resident in every
session that never runs a search. The idle watchdog closes it again after a
quiet period; the next call transparently relaunches.

Async API only -- playwright.sync_api deadlocks inside a running event loop.
"""

from __future__ import annotations

import asyncio
import atexit
import contextlib
import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from playwright.async_api import Browser, BrowserContext, async_playwright

from webresearch.config import settings

log = logging.getLogger(__name__)

# Bounds concurrent page loads (the `research` tool fans out).
page_semaphore = asyncio.Semaphore(3)

_BLOCKED_RESOURCES = {"image", "media", "font"}

_STEALTH_INIT = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
"""


async def _block_heavy(route) -> None:
    if route.request.resource_type in _BLOCKED_RESOURCES:
        await route.abort()
    else:
        await route.continue_()


class BrowserManager:
    def __init__(self) -> None:
        self._pw = None
        self._browser: Browser | None = None
        self._lock = asyncio.Lock()
        self._watchdog: asyncio.Task | None = None
        self._last_used = time.monotonic()

    async def _ensure(self) -> Browser:
        async with self._lock:
            if self._browser is None or not self._browser.is_connected():
                log.info("launching chromium (headless=%s)", settings.headless)
                self._pw = await async_playwright().start()
                self._browser = await self._pw.chromium.launch(
                    headless=settings.headless,
                    args=[
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--disable-blink-features=AutomationControlled",
                    ],
                )
                if self._watchdog is None or self._watchdog.done():
                    self._watchdog = asyncio.create_task(self._idle_loop())
            return self._browser

    async def _idle_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(30)
                if self._browser is None:
                    continue
                if time.monotonic() - self._last_used > settings.browser_idle_secs:
                    log.info("closing idle chromium")
                    await self.close()
                    return
        except asyncio.CancelledError:
            pass

    @asynccontextmanager
    async def context(self, *, block_heavy: bool = True) -> AsyncIterator[BrowserContext]:
        browser = await self._ensure()
        ctx = await browser.new_context(
            user_agent=settings.user_agent,
            viewport={"width": 1366, "height": 900},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={"Accept-Language": "en-US,en;q=0.9"},
        )
        await ctx.add_init_script(_STEALTH_INIT)
        if block_heavy:
            # 3-5x faster loads; we only ever want the text.
            await ctx.route("**/*", _block_heavy)
        self._last_used = time.monotonic()
        try:
            yield ctx
        finally:
            self._last_used = time.monotonic()
            with contextlib.suppress(Exception):
                await ctx.close()

    async def close(self) -> None:
        async with self._lock:
            if self._watchdog and not self._watchdog.done():
                self._watchdog.cancel()
                self._watchdog = None
            if self._browser is not None:
                with contextlib.suppress(Exception):
                    await self._browser.close()
                self._browser = None
            if self._pw is not None:
                with contextlib.suppress(Exception):
                    await self._pw.stop()
                self._pw = None


manager = BrowserManager()


def _atexit_close() -> None:
    # Last-ditch guard against orphaned Chromium if the server is hard-killed.
    if manager._browser is None:
        return
    with contextlib.suppress(Exception):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(manager.close())
        loop.close()


atexit.register(_atexit_close)
