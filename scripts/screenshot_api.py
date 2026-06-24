#!/usr/bin/env python3
"""
Создать скриншоты API интерфейса через Swagger UI.
"""

import asyncio
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Установите playwright: pip install playwright")
    print("Затем запустите: playwright install")
    exit(1)


async def take_screenshots() -> None:
    """Создать скриншоты Swagger UI."""
    output_dir = (
        Path(__file__).parent.parent / "docs" / "assets" / "screenshots"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 800})

        try:
            # Перейти на Swagger UI
            await page.goto(
                "http://localhost:5000/api/docs", wait_until="networkidle"
            )
            await page.screenshot(
                path=str(output_dir / "swagger-ui.png"), full_page=False
            )
            print(
                f"Скриншот Swagger UI сохранён: {output_dir / 'swagger-ui.png'}"
            )
        except Exception as e:
            print(f"Ошибка при создании скриншота Swagger: {e}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(take_screenshots())
