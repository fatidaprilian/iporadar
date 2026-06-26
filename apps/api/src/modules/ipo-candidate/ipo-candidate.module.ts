import { Module } from '@nestjs/common';
import { TypeOrmModule } from '@nestjs/typeorm';
import {
  IpoCandidate,
  Fundamental,
  PriceData,
  NewsArticle,
} from '../../entities/index.js';
import { IpoCandidateController } from './ipo-candidate.controller.js';
import { IpoCandidateService } from './ipo-candidate.service.js';

@Module({
  imports: [
    TypeOrmModule.forFeature([
      IpoCandidate,
      Fundamental,
      PriceData,
      NewsArticle,
    ]),
  ],
  controllers: [IpoCandidateController],
  providers: [IpoCandidateService],
  exports: [IpoCandidateService],
})
export class IpoCandidateModule {}
