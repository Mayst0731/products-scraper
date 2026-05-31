"""
Extracts Taobao cookies from your existing logged-in Chrome browser
and saves them as session_state.json for use by taobao_shop_scraper.py.

No login needed — reuses the session you already have in Chrome.

Usage:
    python extract_cookies.py
    python extract_cookies.py --browser firefox   # if you use Firefox

Requirements:
    pip install browser-cookie3
"""
import argparse
import glob
import json
import os
import time

SESSION_FILE = "session_state.json"

# All Taobao-related domains whose cookies matter for authentication
TAOBAO_DOMAINS = [
    "taobao.com",
    "world.taobao.com",
    "login.taobao.com",
    "s.taobao.com",
    "alipay.com",
    "alicdn.com",
]


def find_best_chrome_profile() -> str:
    """Return the Cookies file path from whichever Chrome profile has the most Taobao cookies."""
    import browser_cookie3

    base = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    candidates = sorted(glob.glob(f"{base}/*/Cookies"))

    best_file, best_count = None, 0
    for cookie_file in candidates:
        try:
            jar = browser_cookie3.chrome(cookie_file=cookie_file, domain_name="taobao.com")
            count = sum(1 for _ in jar)
            profile = cookie_file.replace(base + "/", "").replace("/Cookies", "")
            if count > 0:
                print(f"  {profile}: {count} Taobao cookies")
            if count > best_count:
                best_count, best_file = count, cookie_file
        except Exception:
            continue

    return best_file


def extract(browser: str) -> list:
    import browser_cookie3

    cookies = []
    seen = set()

    if browser == "chrome":
        print("Scanning Chrome profiles for Taobao cookies...")
        cookie_file = find_best_chrome_profile()
        if not cookie_file:
            return []
        print(f"Using: {cookie_file}")
        print()
        for domain in TAOBAO_DOMAINS:
            try:
                jar = browser_cookie3.chrome(cookie_file=cookie_file, domain_name=domain)
                for c in jar:
                    key = (c.name, c.domain, c.path)
                    if key in seen:
                        continue
                    seen.add(key)
                    cookies.append({
                        "name":     c.name,
                        "value":    c.value,
                        "domain":   c.domain if c.domain.startswith(".") else f".{c.domain}",
                        "path":     c.path or "/",
                        "expires":  int(c.expires) if c.expires else int(time.time()) + 86400 * 30,
                        "httpOnly": False,
                        "secure":   bool(c.secure),
                        "sameSite": "Lax",
                    })
            except Exception as e:
                print(f"  Warning: could not read '{domain}' cookies — {e}")
    else:
        extractors = {
            "firefox": browser_cookie3.firefox,
            "safari":  browser_cookie3.safari,
            "edge":    browser_cookie3.edge,
        }
        if browser not in extractors:
            raise ValueError(f"Unsupported browser '{browser}'. Choose: chrome, firefox, safari, edge")
        for domain in TAOBAO_DOMAINS:
            try:
                jar = extractors[browser](domain_name=domain)
                for c in jar:
                    key = (c.name, c.domain, c.path)
                    if key in seen:
                        continue
                    seen.add(key)
                    cookies.append({
                        "name":     c.name,
                        "value":    c.value,
                        "domain":   c.domain if c.domain.startswith(".") else f".{c.domain}",
                        "path":     c.path or "/",
                        "expires":  int(c.expires) if c.expires else int(time.time()) + 86400 * 30,
                        "httpOnly": False,
                        "secure":   bool(c.secure),
                        "sameSite": "Lax",
                    })
            except Exception as e:
                print(f"  Warning: could not read '{domain}' cookies — {e}")

    return cookies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--browser", default="chrome",
                        choices=["chrome", "firefox", "safari", "edge"],
                        help="Browser to extract cookies from (default: chrome)")
    args = parser.parse_args()

    print(f"Reading Taobao cookies from {args.browser}...")
    print("(macOS may show a Keychain permission prompt — click Allow)")
    print()

    cookies = extract(args.browser)

    if not cookies:
        print("No Taobao cookies found.")
        print("Make sure you are logged into Taobao in your browser, then try again.")
        return

    # Playwright storage_state format
    state = {"cookies": cookies, "origins": []}
    with open(SESSION_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)

    print(f"Saved {len(cookies)} cookies to {SESSION_FILE}")
    print()
    print("You can now run:")
    print("  python taobao_shop_scraper.py https://shop65820053.world.taobao.com/")


if __name__ == "__main__":
    main()
