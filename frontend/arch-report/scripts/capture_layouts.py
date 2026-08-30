"""Capture the dev report once with each registered layout engine."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from urllib.parse import urlencode

from playwright.async_api import async_playwright

METHODS = ("layered", "radial", "grid")
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "plans/arch/wip/layout-ab"


async def capture(*, url: str, output: Path) -> None:
    """Capture every method against a running Vite development server."""
    output.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1440, "height": 900})
        errors: list[str] = []
        page.on(
            "console",
            lambda message: (
                errors.append(message.text) if message.type == "error" else None
            ),
        )
        for method in METHODS:
            errors.clear()
            target = f"{url.rstrip('/')}?{urlencode({'layout': method})}"
            await page.goto(target, wait_until="networkidle")
            layout_select = page.locator("select[aria-label='Layout']")
            if await layout_select.count():
                await layout_select.select_option(method)
            await page.locator(".react-flow__node").first.wait_for()
            await page.evaluate(
                "() => new Promise(resolve => requestAnimationFrame(() => "
                "requestAnimationFrame(resolve)))"
            )
            await page.screenshot(
                path=output / f"{method}.png",
                full_page=True,
            )
            if errors:
                raise RuntimeError(f"{method} logged console errors: {errors}")
        await browser.close()


def main() -> None:
    """Run the layout capture command."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:5173")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    asyncio.run(capture(url=args.url, output=args.output))


if __name__ == "__main__":
    main()
