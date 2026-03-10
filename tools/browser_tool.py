"""
Browser autónomo de BEEA con screenshots.
Usa Playwright headless para navegar, ejecutar JS, tomar screenshots.
BEEA puede ver lo que hace y mandarlo a Telegram.
"""

import asyncio
import logging
import base64
from typing import Optional
from pathlib import Path

logger = logging.getLogger("beeatrix.browser")

SCREENSHOTS_DIR = Path("memory/screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)


class BrowserTool:
    def __init__(self):
        self._browser = None
        self._page = None
        self._pw = None

    async def _ensure_browser(self):
        if self._browser and self._browser.is_connected():
            return
        try:
            from playwright.async_api import async_playwright
            self._pw = await async_playwright().start()
            self._browser = await self._pw.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--disable-setuid-sandbox",
                ]
            )
            context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (X11; Linux x86_64) Chrome/120.0.0.0 Safari/537.36"
            )
            self._page = await context.new_page()
            logger.info("Browser iniciado correctamente")
        except Exception as e:
            logger.error("Browser init error: %s", e)
            raise

    async def navigate(self, url: str, wait_ms: int = 2000) -> bool:
        await self._ensure_browser()
        try:
            await self._page.goto(url, timeout=30000, wait_until="domcontentloaded")
            await self._page.wait_for_timeout(wait_ms)
            return True
        except Exception as e:
            logger.warning("Navigate error %s: %s", url, e)
            return False

    async def screenshot(self, url: str = None, full_page: bool = False) -> Optional[bytes]:
        """Toma screenshot. Si se da URL, navega primero."""
        try:
            await self._ensure_browser()
            if url:
                await self.navigate(url)
            img = await self._page.screenshot(full_page=full_page)
            return img
        except Exception as e:
            logger.error("Screenshot error: %s", e)
            return None

    async def screenshot_and_save(self, url: str = None, name: str = "screenshot") -> Optional[Path]:
        img = await self.screenshot(url)
        if not img:
            return None
        path = SCREENSHOTS_DIR / f"{name}.png"
        path.write_bytes(img)
        return path

    async def get_text(self, url: str = None) -> Optional[str]:
        """Extrae todo el texto visible de la página."""
        try:
            await self._ensure_browser()
            if url:
                await self.navigate(url)
            text = await self._page.inner_text("body")
            return text[:5000]
        except Exception as e:
            logger.warning("get_text error: %s", e)
            return None

    async def execute_js(self, script: str) -> Optional[str]:
        """Ejecuta JavaScript en la página y retorna el resultado."""
        try:
            await self._ensure_browser()
            result = await self._page.evaluate(script)
            return str(result)
        except Exception as e:
            logger.warning("JS exec error: %s", e)
            return None

    async def click(self, selector: str) -> bool:
        try:
            await self._page.click(selector, timeout=5000)
            return True
        except Exception:
            return False

    async def type_text(self, selector: str, text: str) -> bool:
        try:
            await self._page.fill(selector, text)
            return True
        except Exception:
            return False

    async def get_current_url(self) -> str:
        try:
            return self._page.url
        except Exception:
            return ""

    async def scroll(self, direction: str = "down", pixels: int = 500):
        y = pixels if direction == "down" else -pixels
        await self._page.evaluate(f"window.scrollBy(0, {y})")

    async def close(self):
        try:
            if self._browser:
                await self._browser.close()
            if self._pw:
                await self._pw.stop()
        except Exception:
            pass

    # ── Tareas específicas de trading ─────────────────────────────────────

    async def screenshot_dexscreener(self, token_address: str) -> Optional[bytes]:
        url = f"https://dexscreener.com/solana/{token_address}"
        return await self.screenshot(url, full_page=False)

    async def screenshot_pumpfun(self, mint: str) -> Optional[bytes]:
        url = f"https://pump.fun/{mint}"
        return await self.screenshot(url, full_page=False)

    async def screenshot_birdeye(self, token_address: str) -> Optional[bytes]:
        url = f"https://birdeye.so/token/{token_address}?chain=solana"
        return await self.screenshot(url)


browser_tool = BrowserTool()
