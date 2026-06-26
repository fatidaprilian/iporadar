import { DataSource } from 'typeorm';
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

/**
 * TypeORM data source for CLI operations (migrations).
 * Not used at runtime -- NestJS manages its own connection via TypeOrmModule.
 */
export const AppDataSource = new DataSource({
  type: 'postgres',
  url:
    process.env.DATABASE_URL ??
    'postgresql://iporadar:iporadar_dev@localhost:5432/iporadar',
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
  migrations: ['./migrations/*.ts'],
  synchronize: false,
  logging: ['error'],
});
