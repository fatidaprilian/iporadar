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

TIER_1_UNDERWRITERS = [
    "mandiri sekuritas",
    "bca sekuritas",
    "indo premier sekuritas",
    "bri danareksa",
    "ubs securities",
    "trimegah sekuritas",
    "citi",
    "morgan stanley",
]

TIER_2_UNDERWRITERS = [
    "sinarmas sekuritas",
    "rhb sekuritas",
    "samuel sekuritas",
    "mnc sekuritas",
    "nh korindo sekuritas",
    "sucor sekuritas",
    "artha sekuritas",
    "erdikha",
    "panin sekuritas",
    "kresna sekuritas",
    "phillip sekuritas",
]


class ScraperSource(str, Enum):
    EIPO = "eipo"
    DISCOVER = "discover"
    IDX = "idx"
    YFINANCE = "yfinance"
    NEWS = "news"


class RunScraperIn(BaseModel):
    sources: Optional[list[ScraperSource]] = None
    tickers: Optional[list[str]] = None


_scraper_status = {
    "waiting": 0,
    "active": 0,
    "completed": 0,
    "failed": 0,
    "last_run": None,
    "last_error": None,
    "sources_completed": [],
    "candidates_found": 0,
}


def _detect_underwriter_tier(underwriter_name: Optional[str]) -> int:
    if not underwriter_name:
        return 3
    lower = underwriter_name.lower()
    for name in TIER_1_UNDERWRITERS:
        if name in lower:
            return 1
    for name in TIER_2_UNDERWRITERS:
        if name in lower:
            return 2
    return 3


def _run_scraper(sources: list[ScraperSource], tickers: list[str]):
    """Execute scraping in a background thread."""
    import asyncio

    _scraper_status["active"] += 1
    completed_sources = []

    async def _scrape():
        from app.database import SessionLocal
        db = SessionLocal()
        try:
            for source in sources:
                try:
                    if source == ScraperSource.EIPO:
                        await _scrape_eipo(db)
                    elif source == ScraperSource.DISCOVER:
                        await _discover_ipo_from_news(db)
                    elif source == ScraperSource.YFINANCE:
                        await _scrape_yfinance(db, tickers)
                    elif source == ScraperSource.NEWS:
                        await _scrape_news(db, tickers)
                    elif source == ScraperSource.IDX:
                        logger.warning("IDX scraper not yet implemented")
                    completed_sources.append(source.value)
                    logger.info(f"Source {source.value} completed")
                except Exception as e:
                    logger.error(f"Source {source.value} failed: {e}", exc_info=True)
                    _scraper_status["failed"] += 1
                    _scraper_status["last_error"] = f"{source.value}: {str(e)[:200]}"
        finally:
            db.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_scrape())
        _scraper_status["completed"] += 1
        _scraper_status["sources_completed"] = completed_sources
        _scraper_status["last_run"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        logger.error(f"Scraper job failed: {e}", exc_info=True)
        _scraper_status["failed"] += 1
        _scraper_status["last_error"] = str(e)[:200]
    finally:
        _scraper_status["active"] -= 1
        loop.close()


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

    from app.models import IpoCandidate, Fundamental, CandidateStatus
    from app.ml.models import SECTOR_PROFILES

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-features=IsolateOrigins,site-per-process",
                "--no-sandbox",
            ],
        )
        try:
            ctx = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                locale="id-ID",
                timezone_id="Asia/Jakarta",
            )
            await ctx.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3]});
                Object.defineProperty(navigator, 'languages', {get: () => ['id-ID', 'id', 'en-US', 'en']});
                window.chrome = {runtime: {}};
            """)
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
            updated = 0
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

                    uw_tier = _detect_underwriter_tier(underwriter)

                    existing = db.query(IpoCandidate).filter(
                        IpoCandidate.ticker == ticker
                    ).first()

                    if existing:
                        changed = False
                        if offer_price and offer_price != existing.offer_price_idr:
                            existing.offer_price_idr = offer_price
                            changed = True
                        if listing_date and listing_date != existing.listing_date:
                            existing.listing_date = listing_date
                            changed = True
                        if underwriter and underwriter != existing.underwriter:
                            existing.underwriter = underwriter
                            changed = True
                        if sector and sector != existing.sector:
                            existing.sector = sector
                            changed = True
                        if uw_tier != existing.underwriter_tier:
                            existing.underwriter_tier = uw_tier
                            changed = True
                        if company and company != existing.company_name:
                            existing.company_name = company
                            changed = True
                        if share_count and share_count != existing.share_count:
                            existing.share_count = share_count
                            changed = True
                        if changed:
                            db.flush()
                            updated += 1
                            logger.info(f"  Updated: {ticker}")
                        else:
                            logger.info(f"  {ticker} unchanged, skipping")
                        continue

                    candidate = IpoCandidate(
                        id=str(uuid.uuid4()),
                        ticker=ticker,
                        company_name=company or f"PT {ticker} Tbk",
                        sector=sector or "Unknown",
                        listing_date=listing_date or (date.today() + timedelta(days=30)),
                        offer_price_idr=offer_price or 0,
                        share_count=share_count,
                        underwriter=underwriter,
                        underwriter_tier=uw_tier,
                        status=CandidateStatus.UPCOMING,
                    )
                    db.add(candidate)
                    db.flush()

                    profile = SECTOR_PROFILES.get(
                        candidate.sector,
                        SECTOR_PROFILES.get("Industrials", {"sector_avg_pe": 14.0, "sector_avg_pb": 2.2}),
                    )
                    fundamental = Fundamental(
                        id=str(uuid.uuid4()),
                        candidate_id=candidate.id,
                        sector_avg_pe=profile["sector_avg_pe"],
                        sector_avg_pb=profile["sector_avg_pb"],
                    )
                    db.add(fundamental)
                    db.flush()

                    scraped += 1
                    logger.info(f"  Saved: {ticker} - {company}")

                except Exception as e:
                    logger.error(f"  Error parsing card: {e}")

            today = date.today()
            transitioned = db.query(IpoCandidate).filter(
                IpoCandidate.status == CandidateStatus.UPCOMING,
                IpoCandidate.listing_date <= today,
            ).update({"status": CandidateStatus.LISTED})

            db.commit()
            _scraper_status["candidates_found"] = scraped
            logger.info(
                f"e-IPO scraping done. {scraped} new, {updated} updated, "
                f"{transitioned} transitioned to LISTED."
            )

        finally:
            await browser.close()


_NOISE_TICKERS = frozenset({
    "BARU", "JULI", "JUNI", "YANG", "DARI", "HARI", "SIAP", "AKAN", "BISA", "JADI",
    "CNBC", "IHSG", "IPOT", "EMAS", "COIN", "BELI", "JUAL", "LINE", "MATA", "SAJA",
    "BAIK", "LAMA", "RASA", "KALI", "SINI", "JUGA", "SAMA", "DULU", "LAGI", "KITA",
    "TIGA", "ENAM", "LIMA", "DINI", "ANDA", "OLEH", "BANK", "AWAL", "AHIR", "SAAT",
    "BUMN", "DANA", "BLOG", "PIPA", "ASPR", "MDKA", "MERI", "PMUI", "PADI", "BPTR",
    "BISA", "CUAN", "HARU", "DIAM", "SOAL", "MANA", "AGAR", "TAHU", "NAIK",
    "SUPA", "RLCO",
})

_MONTH_MAP = {
    "januari": "01", "februari": "02", "maret": "03", "april": "04",
    "mei": "05", "juni": "06", "juli": "07", "agustus": "08",
    "september": "09", "oktober": "10", "november": "11", "desember": "12",
    "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
    "jun": "06", "jul": "07", "agu": "08", "aug": "08",
    "sep": "09", "okt": "10", "oct": "10",
    "nov": "11", "des": "12", "dec": "12",
}


async def _discover_ipo_from_news(db):
    """Discover upcoming IPO candidates from Google News RSS headlines."""
    import urllib.request
    from urllib.parse import quote

    from app.models import IpoCandidate, Fundamental, CandidateStatus
    from app.ml.models import SECTOR_PROFILES

    _USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )

    logger.info("Starting IPO discovery from Google News RSS...")

    queries = [
        "IPO BEI saham baru listing harga 2026",
        "jadwal IPO BEI 2026 harga penawaran",
        "saham IPO baru melantai BEI",
    ]

    all_headlines: list[str] = []
    for q in queries:
        url = f"https://news.google.com/rss/search?q={quote(q)}&hl=id&gl=ID&ceid=ID:id"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            titles = re.findall(r"<title>(.*?)</title>", body)
            for t in titles:
                clean = t.replace("&amp;", "&").replace("&#39;", "'").strip()
                if clean and "Google" not in clean:
                    all_headlines.append(clean)
        except Exception as e:
            logger.warning(f"  RSS query failed: {e}")

    logger.info(f"Collected {len(all_headlines)} headlines from Google News")

    ticker_pattern = re.compile(r"\b([A-Z]{4})\b")
    discovered_tickers: set[str] = set()
    for h in all_headlines:
        for m in ticker_pattern.findall(h):
            if m not in _NOISE_TICKERS:
                discovered_tickers.add(m)

    logger.info(f"Found {len(discovered_tickers)} potential tickers: {sorted(discovered_tickers)}")

    saved = 0
    updated = 0
    for ticker in sorted(discovered_tickers):
        existing = db.query(IpoCandidate).filter(IpoCandidate.ticker == ticker).first()
        if existing:
            logger.info(f"  {ticker}: already in DB, skipping discovery")
            continue

        details = _extract_ticker_details(ticker, all_headlines)
        if details["headline_count"] < 2:
            logger.info(f"  {ticker}: only {details['headline_count']} mention(s), skipping")
            continue

        # Skip tickers already trading on BEI
        try:
            import yfinance as yf
            tk = yf.Ticker(f"{ticker}.JK")
            hist = tk.history(period="5d", auto_adjust=False)
            if not hist.empty:
                logger.info(f"  {ticker}: already trading on BEI, skipping")
                continue
        except Exception:
            pass

        offer_price = details["offer_price"] or 0
        listing_date_val = details["listing_date"] or (date.today() + timedelta(days=30))
        company_name = details["company_name"] or f"PT {ticker} Tbk"

        candidate = IpoCandidate(
            id=str(uuid.uuid4()),
            ticker=ticker,
            company_name=company_name,
            sector=details.get("sector") or "Industrials",
            listing_date=listing_date_val,
            offer_price_idr=offer_price,
            underwriter=details.get("underwriter"),
            underwriter_tier=_detect_underwriter_tier(details.get("underwriter")),
            status=CandidateStatus.UPCOMING,
        )
        db.add(candidate)
        db.flush()

        sector = candidate.sector
        profile = SECTOR_PROFILES.get(
            sector,
            SECTOR_PROFILES.get("Industrials", {"sector_avg_pe": 14.0, "sector_avg_pb": 2.2}),
        )
        fundamental = Fundamental(
            id=str(uuid.uuid4()),
            candidate_id=candidate.id,
            sector_avg_pe=profile["sector_avg_pe"],
            sector_avg_pb=profile["sector_avg_pb"],
        )
        db.add(fundamental)
        db.flush()

        saved += 1
        logger.info(
            f"  Discovered: {ticker} - {company_name}, "
            f"offer={offer_price or '?'}, listing={listing_date_val}"
        )

    db.commit()
    _scraper_status["candidates_found"] = saved
    logger.info(f"IPO discovery done. {saved} new candidates, {updated} updated.")


def _extract_ticker_details(ticker: str, all_headlines: list[str]) -> dict:
    """Extract offer price, listing date, company name, and underwriter for a ticker from headlines."""
    relevant = [h for h in all_headlines if ticker in h]
    if not relevant:
        return {"headline_count": 0}

    all_text = " ".join(relevant)

    # --- Offer price ---
    offer_price = None
    price_pattern = re.compile(
        rf"(?:harga\s+(?:IPO|penawaran)\s+(?:{ticker}\s+)?Rp\s?\.?\s?(\d[\d.,]*))"
        rf"|(?:{ticker}.*?Rp\s?\.?\s?(\d[\d.,]*)\s*per\s+(?:lembar|saham))"
        rf"|(?:Rp\s?\.?\s?(\d[\d.,]*)\s*per\s+(?:lembar|saham))"
        rf"|(?:harga\s+IPO\s+Rp\s?\.?\s?(\d[\d.,]*))",
        re.IGNORECASE,
    )
    for m in price_pattern.finditer(all_text):
        raw = next((g for g in m.groups() if g), None)
        if raw:
            clean = raw.replace(".", "").replace(",", "")
            if clean.isdigit() and 50 <= int(clean) <= 50000:
                offer_price = int(clean)
                break

    if not offer_price:
        price_simple = re.compile(r"Rp\s?\.?\s?(\d[\d.,]*)", re.IGNORECASE)
        prices = []
        for m in price_simple.finditer(all_text):
            raw = m.group(1).replace(".", "").replace(",", "")
            if raw.isdigit() and 50 <= int(raw) <= 10000:
                prices.append(int(raw))
        if prices:
            from collections import Counter
            most_common = Counter(prices).most_common(1)
            if most_common:
                offer_price = most_common[0][0]

    # --- Listing date ---
    _MONTH_RE = (
        r"jan(?:uari)?|feb(?:ruari)?|mar(?:et)?|apr(?:il)?|me[ij]"
        r"|jun[ie]?|jul[ie]?|agu(?:stus)?|sep(?:tember)?|okt(?:ober)?"
        r"|nov(?:ember)?|des(?:ember)?"
    )

    listing_date_val = None

    # Priority 1: date with listing context + year
    listing_context = re.compile(
        rf"(?:listing|melantai|pencatatan|tercatat|IPO).*?(\d{{1,2}})\s+({_MONTH_RE})\s+(\d{{4}})",
        re.IGNORECASE,
    )
    ctx_match = listing_context.search(all_text)
    if ctx_match:
        d, m, y = ctx_match.group(1), ctx_match.group(2), ctx_match.group(3)
        month_num = _MONTH_MAP.get(m.lower())
        if month_num and int(y) >= 2025:
            try:
                listing_date_val = date(int(y), int(month_num), int(d))
            except ValueError:
                pass

    # Priority 2: date with listing context WITHOUT year (assume current year)
    if not listing_date_val:
        listing_noyear = re.compile(
            rf"(?:listing|melantai|pencatatan|tercatat).*?(\d{{1,2}})\s+({_MONTH_RE})\b",
            re.IGNORECASE,
        )
        ny_match = listing_noyear.search(all_text)
        if ny_match:
            d, m = ny_match.group(1), ny_match.group(2)
            month_num = _MONTH_MAP.get(m.lower())
            if month_num:
                try:
                    listing_date_val = date(date.today().year, int(month_num), int(d))
                except ValueError:
                    pass

    # Priority 3: any date with year in the text
    if not listing_date_val:
        date_pattern = re.compile(
            rf"(\d{{1,2}})\s+({_MONTH_RE})\s+(\d{{4}})",
            re.IGNORECASE,
        )
        for dm in date_pattern.finditer(all_text):
            d, m, y = dm.group(1), dm.group(2), dm.group(3)
            month_num = _MONTH_MAP.get(m.lower())
            if month_num and int(y) >= 2025:
                try:
                    listing_date_val = date(int(y), int(month_num), int(d))
                    break
                except ValueError:
                    continue

    # Priority 4: any date without year (assume current year, must be future)
    if not listing_date_val:
        date_noyear = re.compile(
            rf"(\d{{1,2}})\s+({_MONTH_RE})\b",
            re.IGNORECASE,
        )
        for dm in date_noyear.finditer(all_text):
            d, m = dm.group(1), dm.group(2)
            month_num = _MONTH_MAP.get(m.lower())
            if month_num:
                try:
                    candidate_date = date(date.today().year, int(month_num), int(d))
                    if candidate_date >= date.today() - timedelta(days=7):
                        listing_date_val = candidate_date
                        break
                except ValueError:
                    continue

    # --- Company name ---
    company_name = None
    _bad_names = {"IPO", "Juli", "Agustus", "Mau", "Ini", "Simak", "Hari", "Cek",
                  "Cara", "Saham", "Resmi", "Siap", "Bidik", "Tawarkan", "Tetapkan",
                  "Patok", "Susul", "Incar", "Mulai", "Masih", "Listing", "Melantai",
                  "Ditutup", "Dibuka", "Harga", "Bursa", "Pasar", "Ramai",
                  "Dibanjiri", "Diserbu", "Diborong", "Diminati", "Oversubscribed",
                  "Terakhir", "Besok", "Penawaran", "Umum", "Fakta", "Wajib",
                  "Profil", "Prospek", "Rangkuman", "Data", "Simulasi",
                  "Potensi", "Berapa", "Layak", "Manakah"}
    # Try "PT Name Tbk" pattern first (most reliable)
    pt_pattern = re.compile(rf"(?:PT\s+)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){{1,5}}?)(?:\s+Tbk)", re.IGNORECASE)
    for headline in relevant:
        if ticker in headline:
            m = pt_pattern.search(headline)
            if m:
                name = m.group(1).strip()
                words = name.split()
                first_word = words[0] if words else ""
                if (len(name) > 3
                    and len(words) >= 2
                    and first_word not in _bad_names
                    and all(w not in _bad_names for w in words)
                    and name.lower() != "ditutup"):
                    company_name = f"PT {name} Tbk"
                    break

    if not company_name:
        cn_patterns = [
            re.compile(rf"{ticker}\s+([A-Z][a-z][a-zA-Z\s]{{2,25}}?)(?:\s+IPO|\s+Tbk)"),
            re.compile(rf"IPO\s+{ticker}\s+([A-Z][a-z][a-zA-Z\s]{{2,25}}?)(?:\s*[,:]|\s+di\s+|\s+Rp)"),
            re.compile(rf"Saham\s+(?:IPO\s+)?{ticker}\s+([A-Z][a-z][a-zA-Z\s]{{2,25}}?)(?:\s|,|:)"),
        ]
        for pat in cn_patterns:
            for headline in relevant:
                m = pat.search(headline)
                if m:
                    name = m.group(1).strip()
                    first_word = name.split()[0] if name.split() else ""
                    if len(name) > 3 and first_word not in _bad_names:
                        company_name = f"PT {name} Tbk"
                        break
            if company_name:
                break

    # --- Underwriter ---
    underwriter = None
    _known_underwriters = [
        "Trimegah Sekuritas", "Mandiri Sekuritas", "BCA Sekuritas",
        "Indo Premier Sekuritas", "Sinarmas Sekuritas", "RHB Sekuritas",
        "Samuel Sekuritas", "MNC Sekuritas", "NH Korindo Sekuritas",
        "Sucor Sekuritas", "Mirae Asset Sekuritas", "CGS-CIMB Sekuritas",
        "BNI Sekuritas", "Panin Sekuritas", "Phillip Sekuritas",
        "Kresna Sekuritas", "Panca Global Sekuritas",
    ]
    lower_text_uw = all_text.lower()
    for uw in _known_underwriters:
        if uw.lower() in lower_text_uw:
            underwriter = uw
            break

    if not underwriter:
        uw_pattern = re.compile(
            r"(?:penjamin\s+emisi|underwriter)[:\s]+(?:PT\s+)?([A-Z][a-zA-Z\s]+?Sekuritas[^\s,]*)",
            re.IGNORECASE,
        )
        uw_match = uw_pattern.search(all_text)
        if uw_match:
            underwriter = uw_match.group(1).strip()

    # --- Sector ---
    sector = None
    sector_keywords = {
        "Healthcare": ["medika", "hospital", "diagnostic", "kesehatan", "farmasi", "medis", "prodia", "klinik"],
        "Technology": ["teknologi", "digital", "software", "tech", "data", "fintech"],
        "Consumer Cyclical": ["entertainment", "media", "retail", "fashion", "raffi", "hiburan"],
        "Financial Services": ["bank", "finance", "sekuritas", "asuransi", "multifinance"],
        "Energy": ["energy", "energi", "minyak", "gas", "batu bara", "batubara"],
        "Consumer Staples": ["food", "makanan", "minuman", "consumer", "jeli", "snack"],
        "Industrials": ["logistik", "logistics", "konstruksi", "industri", "manufaktur"],
        "Property": ["property", "properti", "real estate"],
        "Mining": ["mining", "tambang", "nikel", "mineral"],
    }
    lower_text_sec = all_text.lower()
    for sec, keywords in sector_keywords.items():
        if any(kw in lower_text_sec for kw in keywords):
            sector = sec
            break

    return {
        "headline_count": len(relevant),
        "offer_price": offer_price,
        "listing_date": listing_date_val,
        "company_name": company_name,
        "sector": sector,
        "underwriter": underwriter,
    }


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

        end_date = str(date.today() + timedelta(days=1))
        symbol = f"{ticker}.JK"

        try:
            tk = yf.Ticker(symbol)
            hist = tk.history(start=start_date, end=end_date, auto_adjust=False)
        except Exception as e:
            logger.warning(f"  {symbol}: yfinance error: {e}")
            continue

        if hist.empty:
            logger.warning(f"  {symbol}: no data returned")
            continue

        hist.index = hist.index.tz_localize(None)

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


def _parse_prospectus_page1(text: str) -> dict:
    """Extract ticker, company name, listing date, offer price from prospectus page 1."""
    result: dict = {}

    ticker_match = re.search(r'["""]([A-Z]{4})["""]', text)
    if ticker_match:
        result["ticker"] = ticker_match.group(1)

    listing_match = re.search(
        r"Pencatatan\s+Saham.*?:\s*(\d{1,2})\s+(\w+)\s+(\d{4})", text
    )
    if listing_match:
        d, m, y = listing_match.group(1), listing_match.group(2), listing_match.group(3)
        month_num = _MONTH_MAP.get(m.lower())
        if month_num:
            try:
                result["listing_date"] = date(int(y), int(month_num), int(d))
            except ValueError:
                pass

    price_match = re.search(
        r"Harga\s+Penawaran\s+(?:sebesar\s+)?Rp\s?\.?\s?(\d[\d.,]*)",
        text, re.IGNORECASE,
    )
    if price_match:
        raw = price_match.group(1).replace(".", "").replace(",", "").rstrip("-")
        if raw.isdigit() and 50 <= int(raw) <= 50000:
            result["offer_price"] = int(raw)

    name_match = re.search(r"(PT\s+[A-Z][A-Za-z\s]+?Tbk)\.?\s*[\n.].*?Kegiatan Usaha", text, re.DOTALL | re.IGNORECASE)
    if not name_match:
        name_match = re.search(r"DICATATKAN.*?(PT\s+[A-Z][A-Za-z\s]+?Tbk)", text, re.DOTALL | re.IGNORECASE)
    if not name_match:
        name_match = re.search(r"(?:Penawaran Umum|IPO).*?(PT\s+[A-Z].+?\s+Tbk)", text, re.IGNORECASE)
    if name_match:
        name = re.sub(r"\s+", " ", name_match.group(1).strip())
        name = name.title().replace("Pt ", "PT ").replace(" Tbk", " Tbk")
        if "Sekuritas" not in name and "Bursa Efek" not in name and len(name) > 8:
            result["company_name"] = name

    return result


def _parse_prospectus_financials(pages_text: list[str]) -> dict:
    """Extract ROE, D/E, revenue growth, EPS from financial ratio pages."""
    result: dict = {}

    for text in pages_text:
        if not any(kw in text for kw in ("Rasio Keuangan", "ROE", "Rasio Pertumbuhan", "Rasio Usaha")):
            continue

        if "roe" not in result:
            roe_match = re.search(
                r"(?:[Ee]kuitas\s*\(ROE\)?\*{0,2}\)?)\s+([\d.,]+)[%x]?",
                text, re.IGNORECASE,
            )
            if roe_match:
                try:
                    val = float(roe_match.group(1).replace(",", "."))
                    result["roe"] = val / 100.0 if val > 1 else val
                except ValueError:
                    pass

        if "debt_to_equity" not in result:
            de_match = re.search(
                r"[Ll]iabilitas[\s/]+(?:terhadap\s+)?(?:[Jj]umlah\s+)?[Ee]kuitas\s*(?:\(x\)\s*)?([\d.,]+)",
                text,
            )
            if de_match:
                try:
                    val = float(de_match.group(1).replace(",", "."))
                    if val < 50:
                        result["debt_to_equity"] = val
                except ValueError:
                    pass

        if "revenue_growth" not in result:
            growth_section = re.search(r"Rasio Pertumbuhan.*?(?:Rasio Usaha|Rasio Keuangan|Rasio Efisiensi|Rasio Aktivitas|Laba usaha|Laba kotor|Total [Ee]kuitas)", text, re.DOTALL)
            if not growth_section:
                gs_start = text.find("Rasio Pertumbuhan")
                if gs_start >= 0:
                    growth_section = re.match(".*", text[gs_start:gs_start + 500], re.DOTALL)
            if growth_section:
                rev_match = re.search(r"(?:Pendapatan|Penjualan\s+bersih)\s*(?:neto\s*)?[\*\)]*\s+([-\d.,()%x]+)", growth_section.group(0))
            else:
                rev_match = None
            if rev_match:
                raw = rev_match.group(1).replace(",", ".").replace("%", "").replace("x", "").strip("()")
                if rev_match.group(1).startswith("("):
                    raw = "-" + raw
                try:
                    val = float(raw)
                    result["revenue_growth"] = val / 100.0 if abs(val) > 1 else val
                except ValueError:
                    pass

        if "eps" not in result:
            eps_match = re.search(
                r"(?:[Ll]aba\s+(?:per\s+saham|bersih\s+per\s+saham)\s*(?:dasar|dilusi)?|EPS)\s*(?:\(Rp\))?\s*(?:[\*\)]*\s+)?([\d.,]+)",
                text,
            )
            if eps_match:
                try:
                    val = float(eps_match.group(1).replace(",", "."))
                    if 0.1 <= val <= 50000:
                        result["eps"] = val
                except ValueError:
                    pass

    return result


def _parse_prospectus_underwriter(pages_text: list[str]) -> str | None:
    """Extract underwriter name from early pages of prospectus."""
    for text in pages_text:
        uw_match = re.search(
            r"PT\s+([A-Za-z\s]+?Sekuritas[A-Za-z\s]*?)(?:[,.\n]|Penjamin)",
            text,
        )
        if uw_match:
            name = f"PT {uw_match.group(1).strip()}"
            if len(name) > 10:
                return name
    return None


def _scrape_prospectus(db):
    """Fetch prospectus PDFs from e-ipo.co.id and extract real fundamentals."""
    import os
    import tempfile
    import time

    from curl_cffi import requests as cffi_requests
    import pdfplumber

    from app.models import IpoCandidate, Fundamental, CandidateStatus

    upcoming = db.query(IpoCandidate).filter(
        IpoCandidate.status == CandidateStatus.UPCOMING
    ).all()

    if not upcoming:
        logger.info("No upcoming candidates — skipping prospectus scrape")
        return

    upcoming_tickers = {c.ticker: c for c in upcoming}
    logger.info(f"Prospectus scrape: looking for {list(upcoming_tickers.keys())}")

    matched = 0
    id_start = max(330, 353 - 20)
    id_end = 353 + 10

    for pid in range(id_end, id_start - 1, -1):
        if not upcoming_tickers:
            break

        url = f"https://e-ipo.co.id/id/pipeline/get-propectus-file?id={pid}&type="
        try:
            resp = cffi_requests.get(url, impersonate="chrome", timeout=30)
        except Exception as e:
            logger.info(f"  Prospectus ID {pid}: request failed: {e}")
            continue

        if resp.status_code != 200:
            logger.debug(f"  Prospectus ID {pid}: HTTP {resp.status_code}")
            continue
        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type.lower():
            logger.info(f"  Prospectus ID {pid}: not PDF (content-type={content_type}, size={len(resp.content)})")
            continue

        cd = resp.headers.get("content-disposition", "").lower()
        ticker = None
        for t in upcoming_tickers:
            if t.lower() in cd:
                ticker = t
                break

        if not ticker:
            cd_words = set(re.findall(r"[a-z]{3,}", cd))
            for t, c in upcoming_tickers.items():
                name_words = set(
                    w.lower() for w in (c.company_name or "").split()
                    if len(w) > 2 and w.upper() not in ("PT", "TBK")
                )
                if name_words & cd_words:
                    ticker = t
                    break

        tmp_path = None
        try:
            fd, tmp_path = tempfile.mkstemp(suffix=".pdf")
            os.close(fd)
            with open(tmp_path, "wb") as f:
                f.write(resp.content)

            with pdfplumber.open(tmp_path) as pdf:
                if len(pdf.pages) < 5:
                    logger.info(f"  Prospectus ID {pid}: only {len(pdf.pages)} pages, skipping")
                    continue

                page1_text = pdf.pages[0].extract_text() or ""
                p1_data = _parse_prospectus_page1(page1_text)

                if not ticker:
                    ticker = p1_data.get("ticker")
                if not ticker and p1_data.get("company_name"):
                    pdf_name = p1_data["company_name"].upper()
                    for t, c in upcoming_tickers.items():
                        db_name = (c.company_name or "").upper()
                        db_words = [w for w in db_name.replace("PT", "").replace("TBK", "").split() if len(w) > 2]
                        pdf_words = [w for w in pdf_name.replace("PT", "").replace("TBK", "").split() if len(w) > 2]
                        if any(w in pdf_words for w in db_words) or any(w in db_name for w in pdf_words[:2]):
                            ticker = t
                            break
                if not ticker or ticker not in upcoming_tickers:
                    logger.info(f"  Prospectus ID {pid}: ticker '{ticker}' not matched (cd='{cd}')")
                    continue

                candidate = upcoming_tickers[ticker]

                uw_pages = [pdf.pages[i].extract_text() or "" for i in range(1, min(10, len(pdf.pages)))]
                underwriter = _parse_prospectus_underwriter(uw_pages)

                fin_pages = [pdf.pages[i].extract_text() or "" for i in range(10, min(35, len(pdf.pages)))]
                financials = _parse_prospectus_financials(fin_pages)

            updated = []

            if p1_data.get("listing_date"):
                candidate.listing_date = p1_data["listing_date"]
                updated.append(f"listing={p1_data['listing_date']}")

            if p1_data.get("offer_price"):
                candidate.offer_price_idr = p1_data["offer_price"]
                updated.append(f"price={p1_data['offer_price']}")

            if p1_data.get("company_name") and "sekuritas" not in p1_data["company_name"].lower():
                candidate.company_name = p1_data["company_name"]
                updated.append(f"name={p1_data['company_name'][:30]}")

            if underwriter:
                underwriter = re.sub(r"\s+(?:sebagai|selaku|yang).*$", "", underwriter, flags=re.IGNORECASE).strip()
                candidate.underwriter = underwriter
                candidate.underwriter_tier = _detect_underwriter_tier(underwriter)
                updated.append(f"uw={underwriter}")

            fund = candidate.fundamental
            if not fund and financials:
                fund = Fundamental(candidate_id=candidate.id)
                db.add(fund)
                db.flush()
                candidate.fundamental = fund
            if fund and financials:
                if financials.get("roe") is not None:
                    fund.roe = financials["roe"]
                    updated.append(f"ROE={financials['roe']:.2%}")
                if financials.get("debt_to_equity") is not None:
                    fund.debt_to_equity = financials["debt_to_equity"]
                    updated.append(f"D/E={financials['debt_to_equity']:.2f}")
                if financials.get("revenue_growth") is not None:
                    fund.revenue_growth_yoy = financials["revenue_growth"]
                    updated.append(f"rev_g={financials['revenue_growth']:.2%}")
                if financials.get("eps") and candidate.offer_price_idr:
                    pe = candidate.offer_price_idr / financials["eps"]
                    if 0.5 <= pe <= 200:
                        fund.pe_ratio = round(pe, 2)
                        updated.append(f"P/E={pe:.1f}x (EPS={financials['eps']:.1f})")

            if updated:
                matched += 1
                logger.info(f"  Prospectus ID {pid} → {ticker}: {', '.join(updated)}")
                del upcoming_tickers[ticker]

        except Exception as e:
            logger.warning(f"  Prospectus ID {pid}: parse error: {e}")
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

        time.sleep(1)

    db.commit()
    logger.info(f"Prospectus scrape done. {matched} candidates enriched from PDF.")


def _enrich_from_news(db):
    """Re-extract offer price, listing date, underwriter from saved news headlines for upcoming candidates."""
    from app.models import IpoCandidate, NewsArticle, CandidateStatus

    upcoming = db.query(IpoCandidate).filter(
        IpoCandidate.status == CandidateStatus.UPCOMING
    ).all()

    if not upcoming:
        return

    logger.info(f"Enriching {len(upcoming)} upcoming candidates from news headlines...")

    for candidate in upcoming:
        articles = db.query(NewsArticle).filter(
            NewsArticle.candidate_id == candidate.id
        ).all()
        if not articles:
            continue

        headlines = [a.headline for a in articles if a.headline]
        details = _extract_ticker_details(candidate.ticker, headlines)

        updated_fields = []

        if details.get("offer_price") and (not candidate.offer_price_idr or candidate.offer_price_idr == 0):
            candidate.offer_price_idr = details["offer_price"]
            updated_fields.append(f"offer_price={details['offer_price']}")

        default_date = date.today() + timedelta(days=30)
        if details.get("listing_date") and (
            not candidate.listing_date
            or candidate.listing_date == default_date
            or (candidate.listing_date - date.today()).days >= 25
        ):
            candidate.listing_date = details["listing_date"]
            updated_fields.append(f"listing_date={details['listing_date']}")

        if details.get("company_name") and candidate.company_name == f"PT {candidate.ticker} Tbk":
            candidate.company_name = details["company_name"]
            updated_fields.append(f"name={details['company_name']}")

        if details.get("underwriter") and not candidate.underwriter:
            candidate.underwriter = details["underwriter"]
            candidate.underwriter_tier = _detect_underwriter_tier(details["underwriter"])
            updated_fields.append(f"underwriter={details['underwriter']}")

        if updated_fields:
            logger.info(f"  {candidate.ticker}: enriched — {', '.join(updated_fields)}")

    db.commit()
    logger.info("Enrichment done.")


def _run_pipeline(mode: str | None = None):
    """Full pipeline: discover IPOs → scrape → news → ML analysis.

    mode: "upcoming" = full scrape + upcoming analysis,
          "listed"  = news scrape for listed tickers + listed analysis,
          None      = full scrape + both analyses
    """
    import asyncio

    _scraper_status["active"] += 1
    completed_sources = []

    async def _pipeline():
        from app.database import SessionLocal
        from app.models import IpoCandidate, CandidateStatus

        db = SessionLocal()
        try:
            if mode != "listed":
                await _discover_ipo_from_news(db)
                completed_sources.append("discover")

                await _scrape_eipo(db)
                completed_sources.append("eipo")

                _scrape_prospectus(db)
                completed_sources.append("prospectus")

                upcoming = db.query(IpoCandidate).filter(
                    IpoCandidate.status == CandidateStatus.UPCOMING
                ).all()
                upcoming_tickers = [c.ticker for c in upcoming]

                if upcoming_tickers:
                    await _scrape_news(db, upcoming_tickers)
                    completed_sources.append("news_upcoming")

                    _enrich_from_news(db)
                    completed_sources.append("enrich")
                else:
                    logger.info("No upcoming candidates — skipping upcoming news scrape")

            if mode != "upcoming":
                listed = db.query(IpoCandidate).filter(
                    IpoCandidate.status == CandidateStatus.LISTED
                ).all()
                listed_tickers = [c.ticker for c in listed]

                if listed_tickers:
                    await _scrape_news(db, listed_tickers)
                    completed_sources.append("news_listed")
                else:
                    logger.info("No listed candidates — skipping listed news scrape")

        finally:
            db.close()

        from app.api.v1.analysis import _run_analysis
        from app.database import SessionLocal as SL2
        from app.models import AnalysisRun, RunStatus, TriggerType

        db2 = SL2()
        try:
            if mode != "listed":
                upcoming_count = db2.query(IpoCandidate).filter(
                    IpoCandidate.status == CandidateStatus.UPCOMING
                ).count()
                if upcoming_count > 0:
                    run_up = AnalysisRun(
                        status=RunStatus.QUEUED,
                        top_n=min(upcoming_count, 10),
                        trigger_type=TriggerType.MANUAL,
                    )
                    db2.add(run_up)
                    db2.commit()
                    db2.refresh(run_up)
                    _run_analysis(run_up.id, None, min(upcoming_count, 10), mode="upcoming")
                    completed_sources.append("analysis_upcoming")
                    logger.info(f"Upcoming analysis done: {upcoming_count} candidates")

            if mode != "upcoming":
                listed_count = db2.query(IpoCandidate).filter(
                    IpoCandidate.status == CandidateStatus.LISTED
                ).count()
                if listed_count > 0:
                    run_bt = AnalysisRun(
                        status=RunStatus.QUEUED,
                        top_n=min(listed_count, 10),
                        trigger_type=TriggerType.MANUAL,
                    )
                    db2.add(run_bt)
                    db2.commit()
                    db2.refresh(run_bt)
                    _run_analysis(run_bt.id, None, min(listed_count, 10), mode="listed")
                    completed_sources.append("analysis_listed")
                    logger.info(f"Listed analysis done: {listed_count} candidates")

        finally:
            db2.close()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_pipeline())
        _scraper_status["completed"] += 1
        _scraper_status["sources_completed"] = completed_sources
        _scraper_status["last_run"] = datetime.now(timezone.utc).isoformat()
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        _scraper_status["failed"] += 1
        _scraper_status["last_error"] = str(e)[:200]
    finally:
        _scraper_status["active"] -= 1
        loop.close()


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


class PipelineIn(BaseModel):
    mode: str | None = None


@router.post("/pipeline")
def trigger_pipeline(data: PipelineIn = PipelineIn(), background_tasks: BackgroundTasks = BackgroundTasks()):
    _scraper_status["waiting"] += 1
    background_tasks.add_task(_run_pipeline, data.mode)

    steps = []
    if data.mode != "listed":
        steps.extend(["discover", "eipo", "prospectus", "news_upcoming", "enrich", "analysis_upcoming"])
    if data.mode != "upcoming":
        steps.extend(["news_listed", "analysis_listed"])

    return {
        "status": "queued",
        "pipeline": steps,
        "mode": data.mode or "all",
    }


@router.get("/status")
def get_scraper_status():
    return _scraper_status
