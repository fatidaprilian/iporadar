import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { InjectQueue } from '@nestjs/bullmq';
import { Queue } from 'bullmq';
import { Repository } from 'typeorm';
import {
  AnalysisRun,
  AnalysisResult,
  RunStatus,
  TriggerType,
} from '../../entities/index.js';
import { TriggerAnalysisDto, ListAnalysisQueryDto } from './analysis.dto.js';

@Injectable()
export class AnalysisService {
  constructor(
    @InjectRepository(AnalysisRun)
    private readonly runRepo: Repository<AnalysisRun>,
    @InjectRepository(AnalysisResult)
    private readonly resultRepo: Repository<AnalysisResult>,
    @InjectQueue('analysis')
    private readonly analysisQueue: Queue,
  ) {}

  async trigger(
    dto: TriggerAnalysisDto,
    triggerType: TriggerType = TriggerType.MANUAL,
  ) {
    const run = this.runRepo.create({
      status: RunStatus.QUEUED,
      topN: dto.topN ?? 5,
      triggerType,
    });
    const savedRun = await this.runRepo.save(run);

    await this.analysisQueue.add(
      'run-analysis',
      {
        runId: savedRun.id,
        candidateIds: dto.candidateIds,
        topN: savedRun.topN,
      },
      {
        attempts: 2,
        backoff: { type: 'exponential', delay: 5000 },
        removeOnComplete: 100,
        removeOnFail: 50,
      },
    );

    return {
      jobId: savedRun.id,
      status: savedRun.status,
      message: 'Analysis job queued',
    };
  }

  async getRunStatus(runId: string) {
    const run = await this.runRepo.findOne({ where: { id: runId } });
    if (!run) throw new NotFoundException('Analysis run not found');

    return {
      jobId: run.id,
      status: run.status,
      startedAt: run.startedAt,
      completedAt: run.completedAt,
      errorMessage: run.errorMessage,
    };
  }

  async listResults(query: ListAnalysisQueryDto) {
    const page = query.page ?? 1;
    const limit = query.limit ?? 10;

    const [data, total] = await this.resultRepo.findAndCount({
      relations: { run: true },
      order: { createdAt: 'DESC' },
      skip: (page - 1) * limit,
      take: limit,
    });

    return {
      data: data.map((result) => ({
        id: result.id,
        jobId: result.runId,
        createdAt: result.createdAt,
        candidateCount: result.candidateCount,
        topCandidates: result.topCandidatesSummary,
        prompt: result.prompt,
        status: result.run?.status,
      })),
      meta: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  async getResult(id: string) {
    const result = await this.resultRepo.findOne({
      where: { id },
      relations: { run: true },
    });
    if (!result) throw new NotFoundException('Analysis result not found');

    return {
      id: result.id,
      jobId: result.runId,
      createdAt: result.createdAt,
      candidateCount: result.candidateCount,
      topCandidates: result.topCandidatesSummary,
      prompt: result.prompt,
      status: result.run?.status,
    };
  }

  async markRunProcessing(runId: string) {
    await this.runRepo.update(runId, {
      status: RunStatus.PROCESSING,
      startedAt: new Date(),
    });
  }

  async markRunCompleted(runId: string) {
    await this.runRepo.update(runId, {
      status: RunStatus.COMPLETED,
      completedAt: new Date(),
    });
  }

  async markRunFailed(runId: string, error: string) {
    await this.runRepo.update(runId, {
      status: RunStatus.FAILED,
      completedAt: new Date(),
      errorMessage: error,
    });
  }
}
