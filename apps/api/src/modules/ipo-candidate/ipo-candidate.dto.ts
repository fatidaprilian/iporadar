import {
  IsString,
  IsOptional,
  IsEnum,
  IsInt,
  IsDateString,
  Min,
  Max,
} from 'class-validator';
import { CandidateStatus } from '../../entities/index.js';

export class CreateIpoCandidateDto {
  @IsString()
  ticker!: string;

  @IsString()
  companyName!: string;

  @IsString()
  sector!: string;

  @IsDateString()
  listingDate!: string;

  @IsInt()
  @Min(0)
  offerPriceIdr!: number;

  @IsString()
  shareCount!: string;

  @IsString()
  underwriter!: string;

  @IsInt()
  @Min(1)
  @Max(3)
  underwriterTier!: number;

  @IsOptional()
  @IsEnum(CandidateStatus)
  status?: CandidateStatus;
}

export class UpdateIpoCandidateDto {
  @IsOptional()
  @IsString()
  companyName?: string;

  @IsOptional()
  @IsString()
  sector?: string;

  @IsOptional()
  @IsDateString()
  listingDate?: string;

  @IsOptional()
  @IsInt()
  @Min(0)
  offerPriceIdr?: number;

  @IsOptional()
  @IsString()
  shareCount?: string;

  @IsOptional()
  @IsString()
  underwriter?: string;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(3)
  underwriterTier?: number;

  @IsOptional()
  @IsEnum(CandidateStatus)
  status?: CandidateStatus;
}

export class ListCandidatesQueryDto {
  @IsOptional()
  @IsEnum(CandidateStatus)
  status?: CandidateStatus;

  @IsOptional()
  @IsString()
  sector?: string;

  @IsOptional()
  @IsInt()
  @Min(1)
  page?: number = 1;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(100)
  limit?: number = 20;
}
