#!/usr/bin/env python3
"""Validate the e-IPO Playwright scraper against the live website.

Connects to e-ipo.co.id, extracts IPO cards, and prints structured results.
No database writes — pure validation.

Usage:
  python scripts/test_scraper.py
  python scripts/test_scraper.py --headed    # visible browser
  python scripts/test_scraper.py --detail     # also scrape detail pages
"""

import argparse
import asyncio
import json
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
logger = logging.getLogger(__name__)

EIPO_LIST_URL = "https://e-ipo.co.id/en/ipo/index"
EIPO_BASE_URL = "https://e-ipo.co.id"


async def scrape_eipo_list(headed: bool = False, scrape_detail: bool = False):
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        sys.exit(1)

    results = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not headed)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        logger.info(f"Navigating to {EIPO_LIST_URL}")
        try:
            response = await page.goto(EIPO_LIST_URL, wait_until="networkidle", timeout=30_000)
        except Exception as e:
            logger.error(f"Failed to load page: {e}")
            await browser.close()
            return results

        if response:
            logger.info(f"HTTP {response.status}")
            if response.status != 200:
                logger.error(f"Unexpected status code: {response.status}")
                body = await page.content()
                logger.error(f"Page content (first 500 chars): {body[:500]}")
                await browser.close()
                return results

        title = await page.title()
        logger.info(f"Page title: {title}")

        card_selectors = [
            ".col-lg-4.col-md-6.col-sm-12",
            ".ipo-card",
            ".card",
            "[class*='ipo']",
        ]

        cards = []
        used_selector = None
        for selector in card_selectors:
            found = await page.locator(selector).all()
            if found:
                cards = found
                used_selector = selector
                break

        logger.info(f"Found {len(cards)} cards using selector: {used_selector or 'none matched'}")

        if not cards:
            logger.warning("No IPO cards found. The page structure may have changed.")
            logger.info("Dumping page HTML for debugging...")
            html = await page.content()
            print(html[:3000])
            await browser.close()
            return results

        for i, card in enumerate(cards):
            data = {"index": i}
            try:
                text = await card.inner_text()
                data["raw_text"] = text.strip()[:200]

                for tag in ["h3", "h4", "h5", ".card-title"]:
                    el = card.locator(tag).first
                    if await el.count():
                        data["ticker"] = (await el.inner_text()).strip()
                        break

                for tag in ["h6", ".card-subtitle", "p:first-of-type"]:
                    el = card.locator(tag).first
                    if await el.count():
                        data["company_name"] = (await el.inner_text()).strip()
                        break

                for tag in ["p.mb-0", ".sector", "p:last-of-type"]:
                    el = card.locator(tag).first
                    if await el.count():
                        data["sector"] = (await el.inner_text()).strip()
                        break

                link = card.locator("a").first
                if await link.count():
                    href = await link.get_attribute("href")
                    if href and not href.startswith("http"):
                        href = EIPO_BASE_URL + href
                    data["detail_url"] = href

            except Exception as e:
                data["error"] = str(e)

            results.append(data)

        if scrape_detail and results:
            logger.info("Scraping detail pages...")
            for item in results:
                url = item.get("detail_url")
                if not url:
                    continue

                logger.info(f"  Detail page: {url}")
                try:
                    await page.goto(url, wait_until="networkidle", timeout=20_000)
                    detail_text = await page.inner_text("body")
                    lines = [l.strip() for l in detail_text.split("\n") if l.strip()]

                    for line in lines:
                        lower = line.lower()
                        if "listing date" in lower or "tanggal pencatatan" in lower:
                            item["listing_date_raw"] = line
                        elif "offer price" in lower or "harga penawaran" in lower:
                            item["offer_price_raw"] = line
                        elif "total shares" in lower or "jumlah saham" in lower:
                            item["share_count_raw"] = line
                        elif "underwriter" in lower or "penjamin" in lower:
                            item["underwriter_raw"] = line

                except Exception as e:
                    item["detail_error"] = str(e)

        await browser.close()

    return results


def main():
    parser = argparse.ArgumentParser(description="Test e-IPO Playwright scraper")
    parser.add_argument("--headed", action="store_true", help="Run browser visibly")
    parser.add_argument("--detail", action="store_true", help="Also scrape detail pages")
    args = parser.parse_args()

    results = asyncio.run(scrape_eipo_list(args.headed, args.detail))

    print(f"\n{'='*60}")
    print(f"SCRAPER VALIDATION REPORT")
    print(f"{'='*60}")
    print(f"Total cards found: {len(results)}")

    for item in results:
        print(f"\n--- Card {item['index']} ---")
        print(f"  Ticker:       {item.get('ticker', 'NOT FOUND')}")
        print(f"  Company:      {item.get('company_name', 'NOT FOUND')}")
        print(f"  Sector:       {item.get('sector', 'NOT FOUND')}")
        print(f"  Detail URL:   {item.get('detail_url', 'NOT FOUND')}")
        if item.get("listing_date_raw"):
            print(f"  Listing Date: {item['listing_date_raw']}")
        if item.get("offer_price_raw"):
            print(f"  Offer Price:  {item['offer_price_raw']}")
        if item.get("underwriter_raw"):
            print(f"  Underwriter:  {item['underwriter_raw']}")
        if item.get("error"):
            print(f"  ERROR:        {item['error']}")

    if results:
        print(f"\n{'='*60}")
        print("RAW JSON OUTPUT:")
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))

    fields = ["ticker", "company_name", "sector", "detail_url"]
    coverage = {f: sum(1 for r in results if r.get(f)) for f in fields}
    print(f"\n{'='*60}")
    print("FIELD COVERAGE:")
    for field, count in coverage.items():
        pct = (count / len(results) * 100) if results else 0
        status = "OK" if pct >= 80 else "WARN" if pct >= 50 else "FAIL"
        print(f"  {field:20s} {count}/{len(results)} ({pct:.0f}%) [{status}]")

    if not results:
        print("\nNO DATA EXTRACTED. Possible causes:")
        print("  1. e-ipo.co.id is blocked (anti-bot / geo-restriction)")
        print("  2. DOM structure has changed")
        print("  3. No active IPO listings at this time")
        sys.exit(1)


if __name__ == "__main__":
    main()
