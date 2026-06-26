import { Injectable, Logger } from '@nestjs/common';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { RunScraperDto, ScraperSource } from './scraper.dto.js';

@Injectable()
export class ScraperService {
  private readonly logger = new Logger(ScraperService.name);

  constructor(
    @InjectQueue('scraper')
    private readonly scraperQueue: Queue,
  ) {}

  async run(dto: RunScraperDto) {
    const sources = dto.sources ?? Object.values(ScraperSource);
    const tickers = dto.tickers ?? [];

    const job = await this.scraperQueue.add(
      'scrape',
      { sources, tickers },
      {
        attempts: 3,
        backoff: { type: 'exponential', delay: 10000 },
        removeOnComplete: 50,
        removeOnFail: 20,
      },
    );

    this.logger.log(
      `Scraper job queued: sources=${sources.join(',')}, tickers=${tickers.join(',') || 'all'}`,
    );

    return {
      jobId: job.id,
      status: 'queued',
      sources,
    };
  }

  async getStatus() {
    const waiting = await this.scraperQueue.getWaitingCount();
    const active = await this.scraperQueue.getActiveCount();
    const completed = await this.scraperQueue.getCompletedCount();
    const failed = await this.scraperQueue.getFailedCount();

    return { waiting, active, completed, failed };
  }
}
