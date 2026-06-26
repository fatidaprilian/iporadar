import { Injectable } from '@nestjs/common';
import { IpoCandidate } from '../../entities/index.js';
import { Prediction } from '../../entities/prediction.entity.js';

interface RankedCandidate {
  candidate: IpoCandidate;
  prediction: Prediction;
  rank: number;
}

/**
 * Generates a structured copy-paste-ready prompt for external LLM analysis.
 * No LLM is integrated in the codebase -- the user copies this prompt
 * and pastes it into Claude, ChatGPT, Gemini, or any LLM with web search.
 */
@Injectable()
export class PromptBuilderService {
  build(rankedCandidates: RankedCandidate[], analysisDate: Date): string {
    const dateStr = analysisDate.toLocaleDateString('id-ID', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
    });

    const candidateBlocks = rankedCandidates
      .map((rc, index) =>
        this.formatCandidate(rc, index + 1, rankedCandidates.length),
      )
      .join('\n\n');

    return `Kamu adalah analis saham IPO Indonesia yang independen dan kritis.
Tugasmu adalah membandingkan kandidat IPO berikut dan memilih SATU
yang paling layak dibeli saat ini berdasarkan analisa menyeluruh.

Tanggal analisa: ${dateStr}

---

PANDUAN BACA DATA:
- Layer 1 Score: probabilitas outperform IHSG di hari pertama listing
- Layer 2 Score: probabilitas outperform IHSG dalam 30 hari post-listing
- Sentiment Score: -1.0 (sangat negatif) sampai 1.0 (sangat positif)
- Composite Rank: ranking final dari sistem ML (1 = terbaik)
- Underwriter Tier: Tier-1 (bulge bracket BEI), Tier-2 (mid), Tier-3 (kecil)

---

KANDIDAT IPO:

${candidateBlocks}

---

INSTRUKSI ANALISA:

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
dan jelaskan alasannya. Jangan memaksakan rekomendasi.

---

OUTPUT FORMAT:

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
investor. Selalu lakukan riset mandiri tambahan sebelum membeli saham.`;
  }

  private formatCandidate(
    rc: RankedCandidate,
    displayIndex: number,
    total: number,
  ): string {
    const c = rc.candidate;
    const p = rc.prediction;
    const f = c.fundamental;

    const l1Score = p.layer1Probability
      ? `${(parseFloat(p.layer1Probability) * 100).toFixed(1)}%`
      : 'N/A';
    const l2Score = p.layer2Probability
      ? `${(parseFloat(p.layer2Probability) * 100).toFixed(1)}%`
      : 'N/A';
    const sentScore = p.sentimentScore ?? 'N/A';
    const compositeScore = p.compositeScore
      ? `${(parseFloat(p.compositeScore) * 100).toFixed(1)}%`
      : 'N/A';

    let fundamentalBlock = '';
    if (f) {
      const lines: string[] = [];
      if (f.peRatio != null) {
        const sectorPe = f.sectorAvgPe
          ? ` (rata-rata sektor: ${f.sectorAvgPe})`
          : '';
        lines.push(`  P/E ratio: ${f.peRatio}${sectorPe}`);
      }
      if (f.pbRatio != null) {
        const sectorPb = f.sectorAvgPb
          ? ` (rata-rata sektor: ${f.sectorAvgPb})`
          : '';
        lines.push(`  P/B ratio: ${f.pbRatio}${sectorPb}`);
      }
      if (f.roe != null)
        lines.push(`  ROE: ${(parseFloat(f.roe) * 100).toFixed(1)}%`);
      if (f.debtToEquity != null)
        lines.push(`  Debt-to-equity: ${f.debtToEquity}`);
      if (f.totalAssetsIdr != null) {
        lines.push(`  Total aset: Rp ${this.formatIdr(f.totalAssetsIdr)}`);
      }
      if (f.revenueGrowthYoy != null) {
        lines.push(
          `  Revenue growth YoY: ${(parseFloat(f.revenueGrowthYoy) * 100).toFixed(1)}%`,
        );
      }
      fundamentalBlock = lines.join('\n');
    }

    return `Kandidat ${displayIndex}:
  Kode: ${c.ticker}
  Nama perusahaan: ${c.companyName}
  Sektor: ${c.sector}
  Tanggal listing: ${c.listingDate}
  Harga penawaran: Rp ${c.offerPriceIdr.toLocaleString('id-ID')}
  Composite rank: ${rc.rank} dari ${total}
  Layer 1 score: ${l1Score} (first-day outperform probability)
  Layer 2 score: ${l2Score} (30-day outperform probability)
  Sentiment score: ${sentScore}
  Composite score: ${compositeScore}
  Underwriter: ${c.underwriter} (Tier-${c.underwriterTier})
${fundamentalBlock}`;
  }

  private formatIdr(value: string): string {
    const num = BigInt(value);
    const trillion = BigInt(1_000_000_000_000);
    const billion = BigInt(1_000_000_000);
    const million = BigInt(1_000_000);

    if (num >= trillion) {
      return `${(Number(num) / Number(trillion)).toFixed(1)} triliun`;
    }
    if (num >= billion) {
      return `${(Number(num) / Number(billion)).toFixed(1)} miliar`;
    }
    if (num >= million) {
      return `${(Number(num) / Number(million)).toFixed(0)} juta`;
    }
    return num.toLocaleString();
  }
}
