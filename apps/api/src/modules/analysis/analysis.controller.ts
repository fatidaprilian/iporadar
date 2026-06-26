import {
  Controller,
  Post,
  Get,
  Param,
  Body,
  Query,
  ParseUUIDPipe,
} from '@nestjs/common';
import { AnalysisService } from './analysis.service.js';
import { TriggerAnalysisDto, ListAnalysisQueryDto } from './analysis.dto.js';

@Controller('analysis')
export class AnalysisController {
  constructor(private readonly analysisService: AnalysisService) {}

  @Post('trigger')
  trigger(@Body() dto: TriggerAnalysisDto) {
    return this.analysisService.trigger(dto);
  }

  @Get(':jobId')
  getStatus(@Param('jobId', ParseUUIDPipe) jobId: string) {
    return this.analysisService.getRunStatus(jobId);
  }

  @Get('results')
  listResults(@Query() query: ListAnalysisQueryDto) {
    return this.analysisService.listResults(query);
  }

  @Get('results/:id')
  getResult(@Param('id', ParseUUIDPipe) id: string) {
    return this.analysisService.getResult(id);
  }
}
