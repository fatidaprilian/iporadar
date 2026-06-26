import { IsOptional, IsArray, IsUUID, IsInt, Min, Max } from 'class-validator';

export class TriggerAnalysisDto {
  @IsOptional()
  @IsArray()
  @IsUUID('4', { each: true })
  candidateIds?: string[];

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(10)
  topN?: number = 5;
}

export class ListAnalysisQueryDto {
  @IsOptional()
  @IsInt()
  @Min(1)
  page?: number = 1;

  @IsOptional()
  @IsInt()
  @Min(1)
  @Max(50)
  limit?: number = 10;
}
