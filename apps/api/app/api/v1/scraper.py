"""Scraper endpoints — trigger scraping and check status.

Ported from NestJS scraper.controller.ts + scraper.processor.ts.
Uses Python Playwright, feedparser, and yfinance (native Python libs).
"""

import logging
from enum import Enum
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()


class ScraperSource(str, Enum):
    EIPO = "eipo"
    IDX = "idx"
    YFINANCE = "yfinance"
    NEWS = "news"


class RunScraperIn(BaseModel):
    sources: Optional[list[ScraperSource]] = None
    tickers: Optional[list[str]] = None


# --- In-memory job tracking (no Redis needed) ---
_scraper_status = {"waiting": 0, "active": 0, "completed": 0, "failed": 0}


def _run_scraper(sources: list[ScraperSource], tickers: list[str]):
    """Execute scraping in a background thread."""
    import asyncio

    _scraper_status["active"] += 1

    async def _scrape():
        for source in sources:
            try:
                if source == ScraperSource.EIPO:
                    await _scrape_eipo(tickers)
                elif source == ScraperSource.YFINANCE:
                    await _scrape_yfinance(tickers)
                elif source == ScraperSource.NEWS:
                    await _scrape_news(tickers)
                elif source == ScraperSource.IDX:
                    logger.warning("IDX scraper not yet implemented")
                logger.info(f"Source {source.value} completed")
            except Exception as e:
                logger.error(f"Source {source.value} failed: {e}")
                _scraper_status["failed"] += 1

    try:
        asyncio.run(_scrape())
        _scraper_status["completed"] += 1
    except Exception as e:
        logger.error(f"Scraper job failed: {e}")
        _scraper_status["failed"] += 1
    finally:
        _scraper_status["active"] -= 1


async def _scrape_eipo(tickers: list[str]):
    """Scrape IPO data from e-ipo.co.id using Playwright."""
    logger.info("Starting e-IPO scraping with Playwright...")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed. Run: pip install playwright && playwright install chromium")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto("https://e-ipo.co.id/en/ipo/index", wait_until="networkidle")

            cards = await page.locator(".col-lg-4.col-md-6.col-sm-12").all()
            logger.info(f"Found {len(cards)} IPO cards on e-IPO")

            for card in cards:
                try:
                    ticker = await card.locator("h3").first.inner_text()
                    company = await card.locator("h6").first.inner_text()
                    sector = await card.locator("p.mb-0").first.inner_text()
                    logger.info(f"Scraped: {ticker} - {company} ({sector})")
                except Exception as e:
                    logger.error(f"Error parsing IPO card: {e}")
        finally:
            await browser.close()


async def _scrape_yfinance(tickers: list[str]):
    """Fetch historical price data from Yahoo Finance."""
    logger.info(f"Starting yfinance scraping for {len(tickers)} tickers...")

    try:
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed. Run: pip install yfinance")
        return

    for ticker in tickers:
        try:
            symbol = f"{ticker}.JK"
            stock = yf.Ticker(symbol)
            hist = stock.history(start="2023-01-01")
            logger.info(f"Fetched {len(hist)} price records for {symbol}")
        except Exception as e:
            logger.error(f"Error fetching yfinance for {ticker}: {e}")


async def _scrape_news(tickers: list[str]):
    """Scrape news headlines from Google News RSS."""
    logger.info(f"Starting news scraping for {len(tickers)} tickers...")

    try:
        import feedparser
    except ImportError:
        logger.error("feedparser not installed. Run: pip install feedparser")
        return

    from urllib.parse import quote

    for ticker in tickers:
        try:
            query = quote(f'"{ticker}" saham OR IPO')
            url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"
            feed = feedparser.parse(url)
            logger.info(f"Found {len(feed.entries)} news items for {ticker}")
        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")


# --- Endpoints ---

@router.post("/run")
def trigger_scraper(data: RunScraperIn, background_tasks: BackgroundTasks):
    sources = data.sources or list(ScraperSource)
    tickers = data.tickers or []

    _scraper_status["waiting"] += 1
    background_tasks.add_task(_run_scraper, sources, tickers)

    return {
        "status": "queued",
        "sources": [s.value for s in sources],
    }


@router.get("/status")
def get_scraper_status():
    return _scraper_status
