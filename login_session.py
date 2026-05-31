"""
Run this once to log in to Taobao and save the session.
The saved session (session_state.json) is reused by taobao_shop_scraper.py.

Usage:
    python login_session.py
"""
import asyncio
import sys
import threading
from playwright.async_api import async_playwright

SESSION_FILE = "session_state.json"
LOGIN_URL = "https://login.taobao.com/member/login.jhtml"


async def save_login_session():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=False,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            locale="zh-CN",
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        await page.goto(LOGIN_URL, wait_until="domcontentloaded")

        print()
        print("=" * 60)
        print("STEP 1: Log in inside the browser window.")
        print("        Use password login (密码登录), SMS, or QR scan.")
        print()
        print("STEP 2: After login, make sure you can see the Taobao")
        print("        homepage (www.taobao.com) in the browser.")
        print()
        print("STEP 3: Come back to THIS terminal and press Enter.")
        print("        The browser will stay open until you do.")
        print("=" * 60)
        print()

        # Block until the user presses Enter in the terminal.
        # Uses a background thread so the async event loop keeps running
        # (keeps the browser alive) while waiting for input.
        done = asyncio.Event()

        def _wait_for_enter():
            sys.stdin.readline()
            asyncio.get_event_loop().call_soon_threadsafe(done.set)

        t = threading.Thread(target=_wait_for_enter, daemon=True)
        t.start()

        sys.stdout.write(">> Press Enter when you are on the Taobao homepage: ")
        sys.stdout.flush()

        await done.wait()

        # Small pause so any final redirects and cookies settle
        await asyncio.sleep(2)

        await context.storage_state(path=SESSION_FILE)
        print(f"\nSession saved to {SESSION_FILE}")
        print("You can now run:")
        print("  python taobao_shop_scraper.py https://shop65820053.world.taobao.com/")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(save_login_session())
