import { PromptBuilderService } from './prompt-builder.service.js';
import {
  IpoCandidate,
  CandidateStatus,
} from '../../entities/ipo-candidate.entity.js';
import { Fundamental } from '../../entities/fundamental.entity.js';
import { Prediction } from '../../entities/prediction.entity.js';

describe('PromptBuilderService', () => {
  let service: PromptBuilderService;

  beforeEach(() => {
    service = new PromptBuilderService();
  });

  function makeCandidate(overrides: Partial<IpoCandidate> = {}): IpoCandidate {
    const candidate = new IpoCandidate();
    Object.assign(candidate, {
      id: '00000000-0000-0000-0000-000000000001',
      ticker: 'TEST',
      companyName: 'PT Test Tbk',
      sector: 'Technology',
      listingDate: '2024-06-15',
      offerPriceIdr: 500,
      shareCount: '1000000000',
      underwriter: 'Mandiri Sekuritas',
      underwriterTier: 1,
      status: CandidateStatus.UPCOMING,
      version: 1,
      createdAt: new Date(),
      updatedAt: new Date(),
      ...overrides,
    });
    return candidate;
  }

  function makeFundamental(overrides: Partial<Fundamental> = {}): Fundamental {
    const f = new Fundamental();
    Object.assign(f, {
      id: '00000000-0000-0000-0000-000000000010',
      candidateId: '00000000-0000-0000-0000-000000000001',
      peRatio: '15.20',
      pbRatio: '2.10',
      roe: '0.1800',
      debtToEquity: '0.4500',
      totalAssetsIdr: '5000000000000',
      revenueIdr: '2000000000000',
      netIncomeIdr: '300000000000',
      revenueGrowthYoy: '0.2500',
      sectorAvgPe: '20.00',
      sectorAvgPb: '3.00',
      reportDate: new Date(),
      createdAt: new Date(),
      ...overrides,
    });
    return f;
  }

  function makePrediction(overrides: Partial<Prediction> = {}): Prediction {
    const p = new Prediction();
    Object.assign(p, {
      id: '00000000-0000-0000-0000-000000000020',
      candidateId: '00000000-0000-0000-0000-000000000001',
      modelVersion: 'v1.0.0',
      layer1Probability: '0.8200',
      layer1Label: 'outperform',
      layer1FeatureImportance: { roe: 0.15, sentimentScore: 0.12 },
      layer2Probability: '0.7100',
      layer2Label: 'outperform',
      layer2FeatureImportance: { rsi: 0.18 },
      sentimentScore: '0.450',
      sentimentMagnitude: '0.780',
      newsCount: 12,
      compositeScore: '0.7200',
      createdAt: new Date(),
      ...overrides,
    });
    return p;
  }

  it('should generate a prompt containing candidate data', () => {
    const candidate = makeCandidate();
    candidate.fundamental = makeFundamental();
    const prediction = makePrediction();

    const prompt = service.build(
      [{ candidate, prediction, rank: 1 }],
      new Date('2024-06-15'),
    );

    expect(prompt).toContain('TEST');
    expect(prompt).toContain('PT Test Tbk');
    expect(prompt).toContain('Technology');
    expect(prompt).toContain('82.0%');
    expect(prompt).toContain('71.0%');
    expect(prompt).toContain('Mandiri Sekuritas');
    expect(prompt).toContain('Tier-1');
    expect(prompt).toContain('P/E ratio: 15.20');
    expect(prompt).toContain('rata-rata sektor: 20.00');
  });

  it('should include the 7-step analysis framework', () => {
    const candidate = makeCandidate();
    const prediction = makePrediction();

    const prompt = service.build(
      [{ candidate, prediction, rank: 1 }],
      new Date('2024-06-15'),
    );

    expect(prompt).toContain('Langkah 1');
    expect(prompt).toContain('Langkah 2');
    expect(prompt).toContain('Langkah 3');
    expect(prompt).toContain('Langkah 4');
    expect(prompt).toContain('Langkah 5');
    expect(prompt).toContain('Langkah 6');
    expect(prompt).toContain('Langkah 7');
    expect(prompt).toContain('TRADING PLAN:');
    expect(prompt).toContain('TIDAK ADA REKOMENDASI');
  });

  it('should include score interpretation guide', () => {
    const candidate = makeCandidate();
    const prediction = makePrediction();

    const prompt = service.build(
      [{ candidate, prediction, rank: 1 }],
      new Date('2024-06-15'),
    );

    expect(prompt).toContain('PANDUAN BACA DATA');
    expect(prompt).toContain('Layer 1 Score');
    expect(prompt).toContain('Composite Rank');
    expect(prompt).toContain('DISCLAIMER');
  });

  it('should format IDR values correctly', () => {
    const candidate = makeCandidate();
    candidate.fundamental = makeFundamental({
      totalAssetsIdr: '5000000000000',
    });
    const prediction = makePrediction();

    const prompt = service.build(
      [{ candidate, prediction, rank: 1 }],
      new Date('2024-06-15'),
    );

    expect(prompt).toContain('5.0 triliun');
  });

  it('should handle multiple candidates with correct ranking', () => {
    const c1 = makeCandidate({ ticker: 'AAA', companyName: 'PT AAA Tbk' });
    const c2 = makeCandidate({
      id: '00000000-0000-0000-0000-000000000002',
      ticker: 'BBB',
      companyName: 'PT BBB Tbk',
    });
    const p1 = makePrediction({ compositeScore: '0.8500' });
    const p2 = makePrediction({
      id: '00000000-0000-0000-0000-000000000021',
      candidateId: c2.id,
      compositeScore: '0.6500',
    });

    const prompt = service.build(
      [
        { candidate: c1, prediction: p1, rank: 1 },
        { candidate: c2, prediction: p2, rank: 2 },
      ],
      new Date('2024-06-15'),
    );

    expect(prompt).toContain('Kandidat 1:');
    expect(prompt).toContain('Kandidat 2:');
    expect(prompt).toContain('1 dari 2');
    expect(prompt).toContain('2 dari 2');
  });
});
