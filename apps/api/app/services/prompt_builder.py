"""Prompt Builder — generates structured copy-paste-ready prompt for external LLM analysis.

Direct port of prompt-builder.service.ts logic. The prompt template text is identical.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional


def _format_idr(value: Optional[int]) -> str:
    """Format IDR amounts to human-readable Indonesian notation."""
    if value is None:
        return "N/A"
    trillion = 1_000_000_000_000
    billion = 1_000_000_000
    million = 1_000_000

    if value >= trillion:
        return f"{value / trillion:.1f} triliun"
    if value >= billion:
        return f"{value / billion:.1f} miliar"
    if value >= million:
        return f"{value / million:.0f} juta"
    return f"{value:,}".replace(",", ".")


def _format_pct(value: Optional[Decimal], multiplier: float = 100.0) -> str:
    if value is None:
        return "N/A"
    return f"{float(value) * multiplier:.1f}%"


def _format_candidate(candidate, prediction, rank: int, total: int) -> str:
    c = candidate
    p = prediction
    f = c.fundamental

    l1_score = _format_pct(p.layer1_probability) if p.layer1_probability else "N/A"
    l2_score = _format_pct(p.layer2_probability) if p.layer2_probability else "N/A"
    sent_score = str(p.sentiment_score) if p.sentiment_score is not None else "N/A"
    composite = _format_pct(p.composite_score) if p.composite_score else "N/A"

    fundamental_lines = []
    if f:
        if f.pe_ratio is not None:
            sector_pe = f" (rata-rata sektor: {f.sector_avg_pe})" if f.sector_avg_pe else ""
            fundamental_lines.append(f"  P/E ratio: {f.pe_ratio}{sector_pe}")
        if f.pb_ratio is not None:
            sector_pb = f" (rata-rata sektor: {f.sector_avg_pb})" if f.sector_avg_pb else ""
            fundamental_lines.append(f"  P/B ratio: {f.pb_ratio}{sector_pb}")
        if f.roe is not None:
            fundamental_lines.append(f"  ROE: {_format_pct(f.roe)}")
        if f.debt_to_equity is not None:
            fundamental_lines.append(f"  Debt-to-equity: {f.debt_to_equity}")
        if f.total_assets_idr is not None:
            fundamental_lines.append(f"  Total aset: Rp {_format_idr(f.total_assets_idr)}")
        if f.revenue_growth_yoy is not None:
            fundamental_lines.append(f"  Revenue growth YoY: {_format_pct(f.revenue_growth_yoy)}")

    fundamental_block = "\n".join(fundamental_lines)

    offer_price = f"{c.offer_price_idr:,}".replace(",", ".") if c.offer_price_idr else "N/A"
    underwriter_info = f"{c.underwriter} (Tier-{c.underwriter_tier})" if c.underwriter else "N/A"

    status_label = "SUDAH LISTING" if getattr(c, 'status', '') == 'listed' else "UPCOMING"
    date_label = "Tanggal listing" if status_label == "SUDAH LISTING" else "Rencana listing"

    return f"""Kandidat {rank}:
  Kode: {c.ticker}
  Nama perusahaan: {c.company_name}
  Status: {status_label}
  Sektor: {c.sector}
  {date_label}: {c.listing_date}
  Harga penawaran: Rp {offer_price}
  Composite rank: {rank} dari {total}
  Layer 1 score: {l1_score} (first-day outperform probability)
  Layer 2 score: {l2_score} (30-day outperform probability)
  Sentiment score: {sent_score}
  Composite score: {composite}
  Underwriter: {underwriter_info}
{fundamental_block}"""


def build_prompt(ranked_candidates: list[dict], analysis_date: datetime) -> str:
    """
    Build the structured LLM prompt.

    ranked_candidates: list of {"candidate": IpoCandidate, "prediction": Prediction, "rank": int}
    """
    date_str = analysis_date.strftime("%d/%m/%Y")
    total = len(ranked_candidates)

    has_upcoming = any(
        rc["candidate"].status == "upcoming" for rc in ranked_candidates
    )
    all_listed = all(
        rc["candidate"].status == "listed" for rc in ranked_candidates
    )

    candidate_blocks = "\n\n".join(
        _format_candidate(rc["candidate"], rc["prediction"], rc["rank"], total)
        for rc in ranked_candidates
    )

    if all_listed:
        preamble = f"""Kamu adalah validator model ML untuk IPO screening.

KONTEKS: Kandidat di bawah adalah IPO BEI yang SUDAH LISTING.
Tugasmu: verifikasi apakah prediksi ML (Layer 1 & Layer 2 score)
sesuai dengan performa aktual saham setelah listing.

Tanggal analisa: {date_str}
Mode: BACKTEST (validasi akurasi ML)"""
    elif has_upcoming:
        preamble = f"""Kamu adalah analis saham IPO Indonesia yang independen dan kritis.
Tugasmu adalah membandingkan kandidat IPO berikut dan memilih SATU
yang paling layak dibeli saat ini berdasarkan analisa menyeluruh.

Tanggal analisa: {date_str}
Mode: LIVE (kandidat aktif)"""
    else:
        preamble = f"""Kamu adalah analis saham IPO Indonesia yang independen dan kritis.
Tugasmu adalah membandingkan kandidat IPO berikut dan memilih SATU
yang paling layak dibeli saat ini berdasarkan analisa menyeluruh.

Tanggal analisa: {date_str}"""

    if all_listed:
        instructions = """INSTRUKSI BACKTEST:

Untuk setiap kandidat:
1. Cari harga saham saat ini dan bandingkan dengan harga penawaran IPO
2. Tentukan apakah saham outperform (naik) atau underperform (turun)
   - Hari pertama: harga close hari pertama vs harga penawaran
   - 30 hari: harga di ~30 hari setelah listing vs harga penawaran

3. Bandingkan dengan prediksi ML:
   - Layer 1 score > 50% = ML prediksi outperform hari pertama
   - Layer 2 score > 50% = ML prediksi outperform 30 hari
   - Cek apakah prediksi ML BENAR atau SALAH

4. Hitung akurasi total model ML dari sampel ini"""

        output_format = """OUTPUT FORMAT:

TABEL VALIDASI:
| Ticker | L1 Score | Prediksi L1 | Aktual Hari-1 | L1 Benar? | L2 Score | Prediksi L2 | Aktual 30d | L2 Benar? |
(isi per kandidat)

AKURASI MODEL:
- Layer 1 (first-day): X dari Y benar (Z%)
- Layer 2 (30-day): X dari Y benar (Z%)

POLA KESALAHAN (jika ada):
[Sebutkan pola: misal "ML terlalu optimis untuk sektor X" atau "ML salah di saham small-cap"]

KESIMPULAN:
[1-2 kalimat: apakah model ML cukup akurat untuk digunakan?]

DISCLAIMER:
Ini adalah backtest validasi model ML, bukan saran investasi."""
    else:
        instructions = """INSTRUKSI ANALISA:

Langkah 1 -- Web Search (WAJIB, lakukan sebelum analisa apapun)
Untuk setiap kandidat, cari:
  - Berita terbaru tentang perusahaan dan sektornya
  - Sentimen media dan analis terhadap IPO ini
  - Kondisi sektor saat ini di BEI
  - Apakah ada isu regulasi, hukum, atau manajemen yang perlu diperhatikan
  - Kondisi IHSG dan market sentiment hari ini

Langkah 2 -- Analisa Fundamental per Kandidat
Gunakan framework berikut untuk setiap kandidat:
  - Valuasi relatif: bandingkan P/E dan P/B terhadap rata-rata sektor
  - Kualitas bisnis: ROE, revenue growth, debt-to-equity
  - Kualitas IPO: reputasi underwriter, besaran offer, free float
  - Red flags wajib cek:
      * P/E lebih dari 2x rata-rata sektor tanpa justifikasi growth
      * ROE negatif atau turun 2 tahun berturut-turut
      * Underwriter Tier-3 dengan track record buruk
      * Debt-to-equity di atas 2.0 untuk sektor non-finansial
      * Berita negatif material dalam 30 hari terakhir

Langkah 3 -- Analisa Teknikal Kontekstual
  - Bagaimana kondisi sektor di IHSG saat ini (bullish/bearish/sideways)?
  - Apakah momentum pasar mendukung entry di IPO baru?
  - Volume dan likuiditas yang diperkirakan berdasarkan ukuran IPO

Langkah 4 -- Interpretasi ML Score
  - Apakah ML score konsisten dengan temuan fundamental dan berita?
  - Jika ML score tinggi tapi ada red flag dari berita, jelaskan konfliknya
  - Jika ML score rendah tapi fundamental kuat, jelaskan alasannya
  - ML score adalah sinyal awal, bukan keputusan final

Langkah 5 -- Perbandingan Eksplisit Antar Kandidat
Buat tabel perbandingan mencakup: valuasi, kualitas bisnis, ML score,
sentiment, red flags, dan kondisi sektor.

Langkah 6 -- Trading Plan & Exit Strategy
Jika ada kandidat yang layak, buatkan skenario trading plan berdasarkan
Harga Penawaran dan volatilitas historis sektor tersebut:
  - Target Price / Take Profit realistis (misal: potensi ARA di hari pertama, atau +20%)
  - Batas Cut Loss ketat (misal: jika breakdown di bawah Harga Penawaran)
  - Berapa lama wajar di-hold (1 hari, 1 minggu, maksimal 30 hari)
Catatan: Jangan menebak harga eksak atau tanggal pasti, gunakan persentase dari harga penawaran.

Langkah 7 -- Keputusan Final
Pilih SATU kandidat terbaik. Jika tidak ada kandidat yang layak
(semua punya red flag material), nyatakan "TIDAK ADA REKOMENDASI"
dan jelaskan alasannya. Jangan memaksakan rekomendasi."""

        output_format = """OUTPUT FORMAT:

REKOMENDASI: [KODE.JK atau "TIDAK ADA REKOMENDASI"]

ALASAN PEMILIHAN:
[Penjelasan 3-5 paragraf mengapa kandidat ini dipilih, mengacu
pada data spesifik, bukan pernyataan generik]

TABEL PERBANDINGAN:
[Tabel semua kandidat vs kandidat terpilih]

TRADING PLAN:
[Skenario Target Profit, batas Cut Loss, dan rentang waktu hold]

RISIKO UTAMA:
[Minimum 3 risiko spesifik, bukan generik "risiko pasar"]

SUMBER BERITA YANG DITEMUKAN:
[List URL atau judul berita yang digunakan dalam analisa]

DISCLAIMER:
Output ini adalah hasil analisa sistem decision support dan bukan
saran investasi. Keputusan beli/tidak beli sepenuhnya tanggung jawab
investor. Selalu lakukan riset mandiri tambahan sebelum membeli saham."""

    return f"""{preamble}

---

PANDUAN BACA DATA:
- Layer 1 Score: probabilitas outperform IHSG di hari pertama listing
- Layer 2 Score: probabilitas outperform IHSG dalam 30 hari post-listing
- Sentiment Score: -1.0 (sangat negatif) sampai 1.0 (sangat positif)
- Composite Rank: ranking final dari sistem ML (1 = terbaik)
- Underwriter Tier: Tier-1 (bulge bracket BEI), Tier-2 (mid), Tier-3 (kecil)

---

KANDIDAT IPO:

{candidate_blocks}

---

{instructions}

---

{output_format}"""
