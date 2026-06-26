import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository } from 'typeorm';
import { Job } from 'bullmq';
import { IpoCandidate, PriceData, NewsArticle } from '../../entities/index.js';
import { ScraperSource } from './scraper.dto.js';

interface ScraperJobData {
  sources: ScraperSource[];
  tickers: string[];
}

/**
 * Background processor for scraping jobs.
 * Phase 1 stubs: actual scraping implementations (e-IPO, yfinance, news)
 * will be added incrementally.
 */
@Processor('scraper')
export class ScraperProcessor extends WorkerHost {
  private readonly logger = new Logger(ScraperProcessor.name);

  constructor(
    @InjectRepository(IpoCandidate)
    private readonly candidateRepo: Repository<IpoCandidate>,
    @InjectRepository(PriceData)
    private readonly priceRepo: Repository<PriceData>,
    @InjectRepository(NewsArticle)
    private readonly newsRepo: Repository<NewsArticle>,
  ) {
    super();
  }

  async process(job: Job<ScraperJobData>): Promise<void> {
    const { sources, tickers } = job.data;
    this.logger.log(`Scraper job started: sources=${sources.join(',')}`);
    // Phase 1: stubs are sync. This await satisfies the async contract
    // and will be replaced by actual async operations in Phase 2.
    await Promise.resolve();

    for (const source of sources) {
      try {
        switch (source) {
          case ScraperSource.EIPO:
            this.scrapeEipo(tickers);
            break;
          case ScraperSource.IDX:
            this.scrapeIdx(tickers);
            break;
          case ScraperSource.YFINANCE:
            this.scrapeYfinance(tickers);
            break;
          case ScraperSource.NEWS:
            this.scrapeNews(tickers);
            break;
        }
        this.logger.log(`Source ${source} completed`);
      } catch (error) {
        const message =
          error instanceof Error ? error.message : 'Unknown error';
        this.logger.error(`Source ${source} failed: ${message}`);
        // Continue with other sources even if one fails
      }
    }

    this.logger.log('Scraper job completed');
  }

  /**
   * Scrape IPO fundamental data from e-IPO.co.id.
   * Phase 1 stub -- actual implementation requires Playwright or BeautifulSoup
   * running in the Python ML service.
   */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private scrapeEipo(_tickers: string[]): void {
    this.logger.warn('e-IPO scraper not yet implemented (Phase 1 stub)');
  }

  /**
   * Scrape financial reports from idx.co.id.
   * Phase 1 stub.
   */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private scrapeIdx(_tickers: string[]): void {
    this.logger.warn('IDX scraper not yet implemented (Phase 1 stub)');
  }

  /**
   * Fetch price data from Yahoo Finance via yfinance.
   * Phase 1 stub -- actual implementation calls the ML service
   * which has yfinance installed.
   */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private scrapeYfinance(_tickers: string[]): void {
    this.logger.warn('yfinance fetcher not yet implemented (Phase 1 stub)');
  }

  /**
   * Scrape news headlines from Google News and financial sites.
   * Phase 1 stub.
   */
  // eslint-disable-next-line @typescript-eslint/no-unused-vars
  private scrapeNews(_tickers: string[]): void {
    this.logger.warn('News scraper not yet implemented (Phase 1 stub)');
  }
}
