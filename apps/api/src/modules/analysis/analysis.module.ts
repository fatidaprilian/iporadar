import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import { BullModule } from '@nestjs/bullmq';
import {
  AnalysisRun,
  AnalysisCandidate,
  AnalysisResult,
  Prediction,
  IpoCandidate,
  Fundamental,
  NewsArticle,
} from '../../entities/index.js';
import { AnalysisController } from './analysis.controller.js';
import { AnalysisService } from './analysis.service.js';
import { PromptBuilderService } from './prompt-builder.service.js';
import { AnalysisProcessor } from './analysis.processor.js';
import { IpoCandidateModule } from '../ipo-candidate/ipo-candidate.module.js';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      AnalysisRun,
      AnalysisCandidate,
      AnalysisResult,
      Prediction,
      IpoCandidate,
      Fundamental,
      NewsArticle,
    ]),
    BullModule.registerQueue({ name: 'analysis' }),
    IpoCandidateModule,
  ],
  controllers: [AnalysisController],
  providers: [AnalysisService, PromptBuilderService, AnalysisProcessor],
  exports: [AnalysisService],
})
export class AnalysisModule {}
