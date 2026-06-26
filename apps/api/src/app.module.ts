import { Module } from '@nestjs/common';
import { ConfigModule, ConfigService } from '@nestjs/config';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BullModule } from '@nestjs/bullmq';

import { IpoCandidateModule } from './modules/ipo-candidate/ipo-candidate.module.js';
import { AnalysisModule } from './modules/analysis/analysis.module.js';
import { ScraperModule } from './modules/scraper/scraper.module.js';
import { HealthModule } from './modules/health/health.module.js';

import {
  IpoCandidate,
  Fundamental,
  PriceData,
  NewsArticle,
  Prediction,
  AnalysisRun,
  AnalysisCandidate,
  AnalysisResult,
} from './entities/index.js';

@Module({
  imports: [
    ConfigModule.forRoot({ isGlobal: true }),

    TypeOrmModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        type: 'postgres' as const,
        url: config.get<string>('DATABASE_URL'),
        entities: [
          IpoCandidate,
          Fundamental,
          PriceData,
          NewsArticle,
          Prediction,
          AnalysisRun,
          AnalysisCandidate,
          AnalysisResult,
        ],
        synchronize: config.get('NODE_ENV') === 'development',
        logging:
          config.get('NODE_ENV') === 'development'
            ? ['error', 'warn']
            : ['error'],
      }),
    }),

    BullModule.forRootAsync({
      inject: [ConfigService],
      useFactory: (config: ConfigService) => ({
        connection: {
          url: config.get<string>('REDIS_URL'),
        },
      }),
    }),

    HealthModule,
    IpoCandidateModule,
    AnalysisModule,
    ScraperModule,
  ],
})
export class AppModule {}
