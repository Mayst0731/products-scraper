# Taobao shop scraper prototype

Purpose: scrape all products for a single Taobao shop URL and save normalized JSON.

Quick start

1. Create a virtualenv and install deps:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Install Playwright browsers:

```bash
playwright install
```

3. Run the scraper (example):

```bash
python run_scraper.py "https://shop65820053.world.taobao.com/?spm=pc_detail.30350276.shop_block.dshopinfo.65507dd68vHKfN" --output shop_output.json --headless
```

Notes

- This prototype uses Playwright to render JS-heavy pages and extract product links reliably.
- For large-scale crawling you should add proxies, persistent sessions (cookies), robust selectors, and rate-limiting.
- Keep Chinese text as-is; no translation is performed.
# products-scraper
