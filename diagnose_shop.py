"""
Diagnostic v2: intercept network requests and inspect product card DOM
to find how world.taobao.com shops serve product data.
"""
import asyncio
import json
from playwright.async_api import async_playwright

SHOP_URL = "https://shop65820053.world.taobao.com/"
SESSION_FILE = "session_state.json"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")

async def main():
    api_calls = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=False)
        ctx = await browser.new_context(
            storage_state=SESSION_FILE, user_agent=UA,
            locale="zh-CN", viewport={"width": 1280, "height": 900}
        )

        # Capture every XHR / fetch that returns JSON
        async def on_response(response):
            url = response.url
            if any(kw in url for kw in ["search", "item", "product", "goods",
                                         "mtop", "api", "json", "list"]):
                try:
                    ct = response.headers.get("content-type", "")
                    if "json" in ct or "javascript" in ct:
                        body = await response.text()
                        if len(body) > 100:
                            api_calls.append({"url": url, "body_preview": body[:500]})
                except Exception:
                    pass

        page = await ctx.new_page()
        page.on("response", on_response)

        print("Loading shop homepage...")
        await page.goto(SHOP_URL, wait_until="networkidle", timeout=30000)

        # Scroll to trigger lazy-loaded products
        for _ in range(6):
            await page.evaluate("window.scrollBy(0, 500)")
            await asyncio.sleep(0.6)

        await asyncio.sleep(2)

        # --- 1. Print intercepted API calls ---
        print(f"\n{'='*60}")
        print(f"Intercepted {len(api_calls)} relevant API calls:")
        for c in api_calls:
            print(f"\n  URL: {c['url'][:120]}")
            print(f"  Body preview: {c['body_preview'][:200]}")

        with open("diag_api_calls.json", "w", encoding="utf-8") as f:
            json.dump(api_calls, f, ensure_ascii=False, indent=2)

        # --- 2. Inspect product card DOM (look for data-* attributes and onclick) ---
        print(f"\n{'='*60}")
        print("Inspecting product card elements...")

        product_info = await page.evaluate("""
            () => {
                const results = [];
                // Try common product card selectors
                const selectors = [
                    '[class*="item"]', '[class*="product"]', '[class*="goods"]',
                    '[class*="card"]', '[data-id]', '[data-item]', '[data-spm]'
                ];
                for (const sel of selectors) {
                    const els = document.querySelectorAll(sel);
                    if (els.length > 2 && els.length < 200) {
                        const sample = els[0];
                        results.push({
                            selector: sel,
                            count: els.length,
                            sample_html: sample.outerHTML.slice(0, 400),
                            sample_attrs: Object.fromEntries(
                                Array.from(sample.attributes).map(a => [a.name, a.value])
                            )
                        });
                    }
                }
                return results;
            }
        """)

        for p in product_info[:8]:
            print(f"\n  Selector: {p['selector']}  (count={p['count']})")
            print(f"  Attrs: {p['sample_attrs']}")
            print(f"  HTML: {p['sample_html'][:200]}")

        # --- 3. Check JS variables for embedded product data ---
        print(f"\n{'='*60}")
        print("Checking JS variables for product data...")
        js_vars = await page.evaluate("""
            () => {
                const candidates = ['__INIT_DATA__', '__initData__', 'g_page_config',
                                    'PAGE_DATA', 'window.__data__', '__DATA__'];
                const found = {};
                for (const v of candidates) {
                    try {
                        const val = eval(v);
                        if (val) found[v] = JSON.stringify(val).slice(0, 300);
                    } catch(e) {}
                }
                return found;
            }
        """)
        for k, v in js_vars.items():
            print(f"  {k}: {v[:200]}")

        await page.screenshot(path="diag_v2.png", full_page=False)
        print("\nScreenshot: diag_v2.png")
        print("API calls saved to: diag_api_calls.json")

        await browser.close()

asyncio.run(main())
