import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BullModule } from '@nestjs/bullmq';
import {
  IpoCandidate,
  Fundamental,
  PriceData,
  NewsArticle,
} from '../../entities/index.js';
import { ScraperController } from './scraper.controller.js';
import { ScraperService } from './scraper.service.js';
import { ScraperProcessor } from './scraper.processor.js';
import { IpoCandidateModule } from '../ipo-candidate/ipo-candidate.module.js';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      IpoCandidate,
      Fundamental,
      PriceData,
      NewsArticle,
    ]),
    BullModule.registerQueue({ name: 'scraper' }),
    IpoCandidateModule,
  ],
  controllers: [ScraperController],
  providers: [ScraperService, ScraperProcessor],
  exports: [ScraperService],
})
export class ScraperModule {}
