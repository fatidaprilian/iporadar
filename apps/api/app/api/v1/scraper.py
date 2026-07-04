"""Scraper endpoints — trigger scraping and check status.

Three sources:
  - eipo:    Playwright scrape of e-ipo.co.id → ipo_candidate table
  - yfinance: Yahoo Finance price history → price_data table
  - news:    Google News RSS + XLM-RoBERTa sentiment → news_article table
"""

import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter()

EIPO_LIST_URL = "https://e-ipo.co.id/en/ipo/index"
EIPO_BASE_URL = "https://e-ipo.co.id"


class ScraperSource(str, Enum):
    EIPO = "eipo"
    IDX = "idx"
    YFINANCE = "yfinance"
    NEWS = "news"


class RunScraperIn(BaseModel):
    sources: Optional[list[ScraperSource]] = None
    tickers: Optional[list[str]] = None


_scraper_status = {"waiting": 0, "active": 0, "completed": 0, "failed": 0}


def _run_scraper(sources: list[ScraperSource], tickers: list[str]):
    """Execute scraping in a background thread."""
    import asyncio

    _scraper_status["active"] += 1

    async def _scrape():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            for source in sources:
                try:
                    if source == ScraperSource.EIPO:
                        await _scrape_eipo(db)
                    elif source == ScraperSource.YFINANCE:
                        await _scrape_yfinance(db, tickers)
                    elif source == ScraperSource.NEWS:
                        await _scrape_news(db, tickers)
                    elif source == ScraperSource.IDX:
                        logger.warning("IDX scraper not yet implemented")
                    logger.info(f"Source {source.value} completed")
                except Exception as e:
                    logger.error(f"Source {source.value} failed: {e}", exc_info=True)
                    _scraper_status["failed"] += 1
        finally:
            db.close()

    try:
        asyncio.run(_scrape())
        _scraper_status["completed"] += 1
    except Exception as e:
        logger.error(f"Scraper job failed: {e}", exc_info=True)
        _scraper_status["failed"] += 1
    finally:
        _scraper_status["active"] -= 1


def _parse_price(text: str) -> Optional[int]:
    """Extract integer price from text like 'Rp 1.500' or '1500'."""
    digits = re.sub(r"[^\d]", "", text)
    return int(digits) if digits else None


def _parse_date(text: str) -> Optional[date]:
    """Try multiple date formats common on e-ipo.co.id."""
    text = text.strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


async def _scrape_eipo(db):
    """Scrape IPO listing data from e-ipo.co.id and persist to ipo_candidate."""
    logger.info("Starting e-IPO scraping...")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.error("Playwright not installed")
        return

    from app.models import IpoCandidate, CandidateStatus

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        try:
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = await ctx.new_page()
            await page.goto(EIPO_LIST_URL, wait_until="networkidle", timeout=30_000)

            card_selectors = [
                ".col-lg-4.col-md-6.col-sm-12",
                ".ipo-card",
                ".card",
            ]
            cards = []
            for sel in card_selectors:
                cards = await page.locator(sel).all()
                if cards:
                    break

            logger.info(f"Found {len(cards)} IPO cards")

            scraped = 0
            for card in cards:
                try:
                    ticker = None
                    company = None
                    sector = None
                    detail_url = None

                    for tag in ["h3", "h4", "h5", ".card-title"]:
                        el = card.locator(tag).first
                        if await el.count():
                            ticker = (await el.inner_text()).strip()
                            break

                    for tag in ["h6", ".card-subtitle"]:
                        el = card.locator(tag).first
                        if await el.count():
                            company = (await el.inner_text()).strip()
                            break

                    for tag in ["p.mb-0", ".sector"]:
                        el = card.locator(tag).first
                        if await el.count():
                            sector = (await el.inner_text()).strip()
                            break

                    link = card.locator("a").first
                    if await link.count():
                        href = await link.get_attribute("href")
                        if href and not href.startswith("http"):
                            href = EIPO_BASE_URL + href
                        detail_url = href

                    if not ticker:
                        continue

                    ticker = ticker.strip().upper()

                    existing = db.query(IpoCandidate).filter(
                        IpoCandidate.ticker == ticker
                    ).first()
                    if existing:
                        logger.info(f"  {ticker} already exists, skipping")
                        continue

                    offer_price = None
                    listing_date = None
                    underwriter = None
                    share_count = None

                    if detail_url:
                        try:
                            await page.goto(detail_url, wait_until="networkidle", timeout=20_000)
                            body_text = await page.inner_text("body")
                            lines = [l.strip() for l in body_text.split("\n") if l.strip()]

                            for line in lines:
                                lower = line.lower()
                                if ("listing date" in lower or "tanggal pencatatan" in lower) and not listing_date:
                                    parts = re.split(r"[:\t]+", line, maxsplit=1)
                                    if len(parts) > 1:
                                        listing_date = _parse_date(parts[1].strip())
                                elif ("offer price" in lower or "harga penawaran" in lower) and offer_price is None:
                                    offer_price = _parse_price(line)
                                elif ("total share" in lower or "jumlah saham" in lower) and share_count is None:
                                    share_count = _parse_price(line)
                                elif ("underwriter" in lower or "penjamin" in lower) and not underwriter:
                                    parts = re.split(r"[:\t]+", line, maxsplit=1)
                                    if len(parts) > 1:
                                        underwriter = parts[1].strip()

                            await page.goto(EIPO_LIST_URL, wait_until="networkidle", timeout=30_000)
                        except Exception as e:
                            logger.warning(f"  {ticker}: detail page failed: {e}")

                    candidate = IpoCandidate(
                        id=str(uuid.uuid4()),
                        ticker=ticker,
                        company_name=company or f"PT {ticker} Tbk",
                        sector=sector or "Unknown",
                        listing_date=listing_date or (date.today() + timedelta(days=30)),
                        offer_price_idr=offer_price or 0,
                        share_count=share_count,
                        underwriter=underwriter,
                        status=CandidateStatus.UPCOMING,
                    )
                    db.add(candidate)
                    db.flush()
                    scraped += 1
                    logger.info(f"  Saved: {ticker} - {company}")

                except Exception as e:
                    logger.error(f"  Error parsing card: {e}")

            db.commit()
            logger.info(f"e-IPO scraping done. {scraped} new candidates saved.")

        finally:
            await browser.close()


async def _scrape_yfinance(db, tickers: list[str]):
    """Fetch price data from Yahoo Finance and persist to price_data."""
    try:
        import pandas as pd
        import yfinance as yf
    except ImportError:
        logger.error("yfinance not installed")
        return

    from app.models import IpoCandidate, PriceData

    if not tickers:
        candidates = db.query(IpoCandidate).all()
        tickers = [c.ticker for c in candidates]

    if not tickers:
        logger.warning("No tickers to fetch price data for")
        return

    logger.info(f"Fetching yfinance data for {len(tickers)} tickers...")

    for ticker in tickers:
        candidate = db.query(IpoCandidate).filter(
            IpoCandidate.ticker == ticker
        ).first()
        if not candidate:
            logger.warning(f"  {ticker}: not found in DB, skipping")
            continue

        existing_count = db.query(PriceData).filter(
            PriceData.candidate_id == candidate.id
        ).count()

        start_date = "2023-01-01"
        if candidate.listing_date:
            start_date = str(candidate.listing_date - timedelta(days=1))

        symbol = f"{ticker}.JK"
        try:
            hist = yf.download(symbol, start=start_date, progress=False, timeout=15)
        except Exception as e:
            logger.warning(f"  {symbol}: yfinance error: {e}")
            continue

        if hist.empty:
            logger.warning(f"  {symbol}: no data returned")
            continue

        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = hist.columns.get_level_values(0)

        saved = 0
        for idx, row in hist.iterrows():
            row_date = idx
            if hasattr(row_date, "date"):
                row_date = row_date.date()

            exists = db.query(PriceData).filter(
                PriceData.candidate_id == candidate.id,
                PriceData.date == row_date,
            ).first()
            if exists:
                continue

            pd_record = PriceData(
                id=str(uuid.uuid4()),
                candidate_id=candidate.id,
                date=row_date,
                open=round(float(row["Open"]), 2),
                high=round(float(row["High"]), 2),
                low=round(float(row["Low"]), 2),
                close=round(float(row["Close"]), 2),
                volume=int(row["Volume"]),
            )
            db.add(pd_record)
            saved += 1

        db.commit()
        logger.info(f"  {symbol}: saved {saved} new price records (had {existing_count})")


async def _scrape_news(db, tickers: list[str]):
    """Scrape Google News RSS, run sentiment analysis, persist to news_article."""
    try:
        import feedparser
    except ImportError:
        logger.error("feedparser not installed")
        return

    import urllib.request
    from urllib.parse import quote

    from app.models import IpoCandidate, NewsArticle

    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )

    if not tickers:
        candidates = db.query(IpoCandidate).all()
        tickers = [c.ticker for c in candidates]

    if not tickers:
        logger.warning("No tickers to fetch news for")
        return

    sentiment_analyzer = None
    try:
        from app.ml.sentiment import get_sentiment_analyzer
        sentiment_analyzer = get_sentiment_analyzer()
    except Exception as e:
        logger.warning(f"Sentiment model unavailable, skipping sentiment: {e}")

    logger.info(f"Fetching news for {len(tickers)} tickers...")

    for ticker in tickers:
        candidate = db.query(IpoCandidate).filter(
            IpoCandidate.ticker == ticker
        ).first()
        if not candidate:
            continue

        query = quote(f'"{ticker}" saham OR IPO')
        url = f"https://news.google.com/rss/search?q={query}&hl=id&gl=ID&ceid=ID:id"

        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                rss_bytes = resp.read()
            feed = feedparser.parse(rss_bytes)
        except urllib.error.HTTPError:
            feed = feedparser.parse(url)
        except Exception as e:
            logger.warning(f"  {ticker}: RSS error: {e}")
            continue

        if not feed.entries:
            logger.info(f"  {ticker}: no news found")
            continue

        headlines = []
        entries_to_save = []

        for entry in feed.entries[:10]:
            headline = entry.get("title", "").strip()
            if not headline:
                continue

            link = entry.get("link", "")
            source = entry.get("source", {}).get("title", "Google News")
            published = entry.get("published_parsed")
            pub_dt = None
            if published:
                try:
                    from time import mktime
                    pub_dt = datetime.fromtimestamp(mktime(published), tz=timezone.utc)
                except Exception:
                    pass

            existing = db.query(NewsArticle).filter(
                NewsArticle.candidate_id == candidate.id,
                NewsArticle.headline == headline,
            ).first()
            if existing:
                continue

            headlines.append(headline)
            entries_to_save.append({
                "headline": headline,
                "url": link,
                "source": source,
                "published_at": pub_dt,
            })

        sentiments = {}
        if sentiment_analyzer and headlines:
            try:
                results = sentiment_analyzer.analyze(headlines)
                for r in results:
                    sentiments[r["text"]] = r
            except Exception as e:
                logger.warning(f"  {ticker}: sentiment analysis failed: {e}")

        saved = 0
        for entry_data in entries_to_save:
            sent = sentiments.get(entry_data["headline"], {})
            article = NewsArticle(
                id=str(uuid.uuid4()),
                candidate_id=candidate.id,
                headline=entry_data["headline"],
                url=entry_data["url"],
                source=entry_data["source"],
                published_at=entry_data["published_at"],
                sentiment_score=sent.get("sentiment_score", 0.0),
                sentiment_label=sent.get("label", "neutral"),
            )
            db.add(article)
            saved += 1

        db.commit()
        logger.info(f"  {ticker}: saved {saved} articles")


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
