"""
Taobao shop scraper — requires a saved session from extract_cookies.py.

Usage:
    # First run (save cookies from Chrome):
    python extract_cookies.py

    # Scrape a shop:
    python taobao_shop_scraper.py https://shop65820053.world.taobao.com/
    python taobao_shop_scraper.py https://shop65820053.world.taobao.com/ --max 50 --output out.json
    python taobao_shop_scraper.py https://shop65820053.world.taobao.com/ --headless
"""
import argparse
import asyncio
import json
import random
import re
from pathlib import Path
from typing import List, Optional, Set
from urllib.parse import urlparse

from playwright.async_api import BrowserContext, async_playwright

from schemas import Product, Shop

SESSION_FILE = "session_state.json"

UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def pause(lo=1.0, hi=2.5):
    await asyncio.sleep(random.uniform(lo, hi))


def extract_shop_id(shop_url: str) -> Optional[str]:
    m = re.search(r"shop(\d+)\.", shop_url)
    return m.group(1) if m else None


def clean_title(raw: str) -> str:
    title = re.sub(r"\s*[-–—]\s*(淘宝网|天猫|Taobao|世界).*$", "", raw).strip()
    title = re.sub(r"^首页[-–—]\s*", "", title).strip()
    return title


def normalize_image(src: str) -> str:
    if src.startswith("//"):
        src = "https:" + src
    return src


def parse_price(raw) -> Optional[str]:
    """Return the first clean price string found."""
    s = str(raw).strip()
    # Keep only the first price if multiple are concatenated (e.g. "25.831.8")
    m = re.match(r"[\d]+\.?\d*", s)
    return m.group(0) if m else (s or None)


# ---------------------------------------------------------------------------
# Shop listing — collect products via API interception
# ---------------------------------------------------------------------------

async def collect_products_via_api(
    context: BrowserContext, shop_url: str, max_products: int
) -> tuple[List[dict], int]:
    """
    Intercept Taobao's internal shop product API (mtop.taobao.shop.simple.item.fetch)
    while scrolling the shop homepage. The API returns itemId, image, title, price,
    and sales count for each product card — cleaner than scraping each product page.
    """
    items: dict = {}   # itemId → dict
    total_cnt: int = 0

    page = await context.new_page()

    async def handle_response(response):
        nonlocal total_cnt
        if "mtop.taobao.shop.simple.item.fetch" not in response.url:
            return
        try:
            text = await response.text()
            text = re.sub(r"^\w+\(", "", text).rstrip(")")
            data = json.loads(text)
            inner = data.get("data") or {}
            if inner.get("totalCnt"):
                total_cnt = int(inner["totalCnt"])
            for item in (inner.get("data") or []):
                iid = str(item.get("itemId", "")).strip()
                if not iid:
                    continue
                items[iid] = {
                    "product_id": iid,
                    "url": f"https://item.taobao.com/item.htm?id={iid}",
                    "title": item.get("title") or item.get("name"),
                    "price": parse_price(item.get("price") or item.get("reservePrice") or ""),
                    "image": normalize_image(item.get("image") or "") or None,
                }
        except Exception:
            pass

    page.on("response", handle_response)

    print(f"  Loading shop: {shop_url}")
    await page.goto(shop_url, wait_until="networkidle", timeout=30000)
    await pause(1.5, 2.5)

    if "login" in page.url:
        print("  Redirected to login — session expired. Re-run extract_cookies.py")
        await page.close()
        return []

    stalled = 0
    prev_count = 0

    while len(items) < max_products:
        if total_cnt and len(items) >= total_cnt:
            print(f"  All {total_cnt} products collected.")
            break

        try:
            if "login" in page.url:
                print("  Redirected to login during scroll — session expired.")
                print("  Re-run: python extract_cookies.py")
                break
            await page.evaluate("window.scrollBy(0, 900)")
        except Exception:
            print("  Page closed unexpectedly — session likely expired.")
            print("  Re-run: python extract_cookies.py")
            break

        await pause(1.0, 1.8)

        if len(items) == prev_count:
            stalled += 1
            if stalled >= 6:
                print("  No new items after 6 scrolls — stopping.")
                break
        else:
            stalled = 0
            prev_count = len(items)
            print(f"  Collected {len(items)}/{total_cnt or '?'} products...")

    try:
        await page.close()
    except Exception:
        pass

    result = list(items.values())[:max_products]
    print(f"Total products from API: {len(result)} (shop total: {total_cnt})")
    return result, total_cnt


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def scrape_shop(shop_url: str, max_products: int, headless: bool) -> Shop:
    session_path = Path(SESSION_FILE)
    if not session_path.exists():
        raise FileNotFoundError(
            f"'{SESSION_FILE}' not found. Run 'python extract_cookies.py' first."
        )

    shop_id = extract_shop_id(shop_url)

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            storage_state=SESSION_FILE,
            user_agent=UA,
            locale="zh-CN",
            viewport={"width": 1280, "height": 900},
        )

        # Resolve brand name from shop homepage title
        home_page = await context.new_page()
        await home_page.goto(shop_url, wait_until="domcontentloaded", timeout=20000)
        brand_name = clean_title(await home_page.title())
        await home_page.close()
        print(f"Brand: {brand_name}  (shop_id={shop_id})")

        print("\n[1/1] Collecting products via API interception...")
        raw_items, total_cnt = await collect_products_via_api(context, shop_url, max_products)

        products = [
            Product(
                product_id=item["product_id"],
                url=item["url"],
                title=item.get("title"),
                price=item.get("price"),
                image=item.get("image"),
            )
            for item in raw_items
        ]

        await browser.close()

    return Shop(shop_id=shop_id, brand_name=brand_name, shop_url=shop_url,
                total_products=total_cnt or None, products=products)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Taobao shop product scraper")
    parser.add_argument(
        "shop_url",
        nargs="?",
        default="https://shop65820053.world.taobao.com/",
        help="Shop homepage URL",
    )
    parser.add_argument("--output", default="shop_output.json", help="Output JSON file")
    parser.add_argument("--max", type=int, default=200, help="Max products to scrape")
    parser.add_argument(
        "--headless", action="store_true", help="Run browser in headless mode"
    )
    args = parser.parse_args()

    shop = asyncio.run(
        scrape_shop(args.shop_url, max_products=args.max, headless=args.headless)
    )

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(
            json.loads(shop.json(by_alias=True, exclude_none=True)),
            f,
            ensure_ascii=False,
            indent=2,
        )

    print(f"\nDone. {len(shop.products)} products saved to {args.output}")
