from playwright.async_api import Browser, Page, Playwright, async_playwright
from agents import Agent, AsyncComputer, Button, ComputerTool, Environment, ModelSettings, Runner, trace
from typing import Union, Dict, Any, List
import base64
import asyncio
# ---------- Key Mappings ----------
CUA_KEY_TO_PLAYWRIGHT_KEY = {
    "/": "Divide", "\\": "Backslash", "alt": "Alt", "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft", "arrowright": "ArrowRight", "arrowup": "ArrowUp",
    "backspace": "Backspace", "capslock": "CapsLock", "cmd": "Meta",
    "ctrl": "Control", "delete": "Delete", "end": "End", "enter": "Enter",
    "esc": "Escape", "home": "Home", "insert": "Insert", "option": "Alt",
    "pagedown": "PageDown", "pageup": "PageUp", "shift": "Shift", "space": " ",
    "super": "Meta", "tab": "Tab", "win": "Meta"
}
# ---------- Local Browser Controlled by Agent ----------
class LocalPlaywrightComputer(AsyncComputer):
    def __init__(self, job_url: str):
        self.job_url = job_url
        self._playwright: Union[Playwright, None] = None
        self._browser: Union[Browser, None] = None
        self._page: Union[Page, None] = None

    async def _get_browser_and_page(self) -> tuple[Browser, Page]:
        width, height = self.dimensions
        browser = await self.playwright.chromium.launch(headless=True, args=[f"--window-size={width},{height}"])
        page = await browser.new_page()
        await page.set_viewport_size({"width": width, "height": height})
        await page.goto(self.job_url)
        return browser, page

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser, self._page = await self._get_browser_and_page()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    @property
    def playwright(self) -> Playwright:
        return self._playwright

    @property
    def browser(self) -> Browser:
        return self._browser

    @property
    def page(self) -> Page:
        return self._page

    @property
    def environment(self) -> Environment:
        return "browser"

    @property
    def dimensions(self) -> tuple[int, int]:
        return (1280, 800)

    async def screenshot(self) -> str:
        png_bytes = await self.page.screenshot(full_page=False)
        return base64.b64encode(png_bytes).decode("utf-8")

    async def click(self, x: int, y: int, button: Button = "left") -> None:
        await self.page.mouse.click(x, y, button=button)

    async def double_click(self, x: int, y: int) -> None:
        await self.page.mouse.dblclick(x, y)

    async def scroll(self, x: int, y: int, scroll_x: int, scroll_y: int) -> None:
        await self.page.mouse.move(x, y)
        await self.page.evaluate(f"window.scrollBy({scroll_x}, {scroll_y})")

    async def type(self, text: str) -> None:
        await self.page.keyboard.type(text)

    async def wait(self) -> None:
        await asyncio.sleep(1)

    async def move(self, x: int, y: int) -> None:
        await self.page.mouse.move(x, y)

    async def keypress(self, keys: list[str]) -> None:
        for key in keys:
            await self.page.keyboard.press(CUA_KEY_TO_PLAYWRIGHT_KEY.get(key.lower(), key))

    async def drag(self, path: list[tuple[int, int]]) -> None:
        if not path:
            return
        await self.page.mouse.move(path[0][0], path[0][1])
        await self.page.mouse.down()
        for px, py in path[1:]:
            await self.page.mouse.move(px, py)
        await self.page.mouse.up()