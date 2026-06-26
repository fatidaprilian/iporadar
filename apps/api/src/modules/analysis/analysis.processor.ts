import { Processor, WorkerHost } from '@nestjs/bullmq';
import { Logger } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, In } from 'typeorm';
import { Job } from 'bullmq';
import { ConfigService } from '@nestjs/config';
import {
  IpoCandidate,
  Prediction,
  AnalysisCandidate,
  AnalysisResult,
} from '../../entities/index.js';
import { AnalysisService } from './analysis.service.js';
import { PromptBuilderService } from './prompt-builder.service.js';
import { IpoCandidateService } from '../ipo-candidate/ipo-candidate.service.js';

interface AnalysisJobData {
  runId: string;
  candidateIds?: string[];
  topN: number;
}

/**
 * Background processor for analysis jobs.
 * Orchestrates: data gathering -> ML service call -> scoring -> prompt generation.
 */
@Processor('analysis')
export class AnalysisProcessor extends WorkerHost {
  private readonly logger = new Logger(AnalysisProcessor.name);

  constructor(
    private readonly analysisService: AnalysisService,
    private readonly promptBuilder: PromptBuilderService,
    private readonly candidateService: IpoCandidateService,
    private readonly config: ConfigService,
    @InjectRepository(Prediction)
    private readonly predictionRepo: Repository<Prediction>,
    @InjectRepository(AnalysisCandidate)
    private readonly analysisCandidateRepo: Repository<AnalysisCandidate>,
    @InjectRepository(AnalysisResult)
    private readonly analysisResultRepo: Repository<AnalysisResult>,
    @InjectRepository(IpoCandidate)
    private readonly ipoCandidateRepo: Repository<IpoCandidate>,
  ) {
    super();
  }

  async process(job: Job<AnalysisJobData>): Promise<void> {
    const { runId, candidateIds, topN } = job.data;
    this.logger.log(`Starting analysis run ${runId}`);

    try {
      await this.analysisService.markRunProcessing(runId);

      // Step 1: Gather candidates
      let candidates: IpoCandidate[];
      if (candidateIds && candidateIds.length > 0) {
        candidates = await this.ipoCandidateRepo.find({
          where: { id: In(candidateIds) },
          relations: { fundamental: true, newsArticles: true },
        });
      } else {
        // Default: upcoming + recently listed
        const upcoming = await this.candidateService.findUpcoming();
        const recent = await this.candidateService.findRecentlyListed(30);
        const seen = new Set<string>();
        candidates = [];
        for (const c of [...upcoming, ...recent]) {
          if (!seen.has(c.id)) {
            seen.add(c.id);
            candidates.push(c);
          }
        }
      }

      if (candidates.length === 0) {
        await this.analysisService.markRunFailed(
          runId,
          'No candidates found for analysis',
        );
        return;
      }

      this.logger.log(`Found ${candidates.length} candidates for analysis`);

      // Step 2: Call ML service for predictions
      const mlServiceUrl = this.config.get<string>('ML_SERVICE_URL');
      const predictions = this.callMlService(mlServiceUrl!, candidates);

      // Step 3: Save predictions and rank
      const savedPredictions: Prediction[] = [];
      for (const prediction of predictions) {
        const saved = await this.predictionRepo.save(prediction);
        savedPredictions.push(saved);
      }

      // Step 4: Rank by composite score, take top N
      const ranked = savedPredictions
        .filter((p) => p.compositeScore != null)
        .sort(
          (a, b) =>
            parseFloat(b.compositeScore!) - parseFloat(a.compositeScore!),
        )
        .slice(0, topN);

      // Step 5: Save analysis candidates
      const analysisCandidates: AnalysisCandidate[] = [];
      for (let i = 0; i < ranked.length; i++) {
        const pred = ranked[i];
        const ac = this.analysisCandidateRepo.create({
          runId,
          candidateId: pred.candidateId,
          predictionId: pred.id,
          compositeRank: i + 1,
        });
        analysisCandidates.push(await this.analysisCandidateRepo.save(ac));
      }

      // Step 6: Build prompt
      const rankedWithCandidates = ranked.map((pred, index) => ({
        candidate: candidates.find((c) => c.id === pred.candidateId)!,
        prediction: pred,
        rank: index + 1,
      }));

      const prompt = this.promptBuilder.build(rankedWithCandidates, new Date());

      // Step 7: Save result
      const topSummary = rankedWithCandidates.map((rc) => ({
        ticker: rc.candidate.ticker,
        companyName: rc.candidate.companyName,
        compositeRank: rc.rank,
        layer1Score: rc.prediction.layer1Probability,
        layer2Score: rc.prediction.layer2Probability,
        sentimentScore: rc.prediction.sentimentScore,
      }));

      await this.analysisResultRepo.save({
        runId,
        candidateCount: candidates.length,
        prompt,
        topCandidatesSummary: topSummary,
      });

      await this.analysisService.markRunCompleted(runId);
      this.logger.log(
        `Analysis run ${runId} completed. ${ranked.length} candidates ranked.`,
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      this.logger.error(`Analysis run ${runId} failed: ${message}`);
      await this.analysisService.markRunFailed(runId, message);
      throw error;
    }
  }

  /**
   * Call the Python ML service for predictions.
   * In Phase 1, this returns placeholder predictions.
   * Phase 2 will implement the actual HTTP call.
   */
  private callMlService(
    _baseUrl: string,
    candidates: IpoCandidate[],
  ): Prediction[] {
    // Phase 1 placeholder: return stub predictions.
    // Phase 2 will replace this with actual HTTP POST to ML service.
    this.logger.warn(
      'ML service call is stubbed (Phase 1). Returning placeholder predictions.',
    );

    return candidates.map((c) => {
      const prediction = this.predictionRepo.create({
        candidateId: c.id,
        modelVersion: 'stub-v0.0.1',
        layer1Probability: '0.5000',
        layer1Label: 'outperform',
        layer1FeatureImportance: null,
        layer2Probability: '0.5000',
        layer2Label: 'outperform',
        layer2FeatureImportance: null,
        sentimentScore: '0.000',
        sentimentMagnitude: '0.000',
        newsCount: c.newsArticles?.length ?? 0,
        compositeScore: '0.5000',
      });
      return prediction;
    });
  }
}
