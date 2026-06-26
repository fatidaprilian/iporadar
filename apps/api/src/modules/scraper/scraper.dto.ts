import { IsOptional, IsArray, IsString, IsEnum } from 'class-validator';

export enum ScraperSource {
  EIPO = 'eipo',
  IDX = 'idx',
  YFINANCE = 'yfinance',
  NEWS = 'news',
}

export class RunScraperDto {
  @IsOptional()
  @IsArray()
  @IsEnum(ScraperSource, { each: true })
  sources?: ScraperSource[];

  @IsOptional()
  @IsArray()
  @IsString({ each: true })
  tickers?: string[];
}
