import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { AnalysisRun } from './analysis-run.entity.js';
import { IpoCandidate } from './ipo-candidate.entity.js';
import { Prediction } from './prediction.entity.js';

@Entity('analysis_candidate')
export class AnalysisCandidate {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'uuid', name: 'run_id' })
  @Index('idx_ac_run')
  runId!: string;

  @Column({ type: 'uuid', name: 'candidate_id' })
  @Index('idx_ac_candidate')
  candidateId!: string;

  @Column({ type: 'uuid', name: 'prediction_id' })
  predictionId!: string;

  @Column({ type: 'smallint', name: 'composite_rank' })
  compositeRank!: number;

  // Relations
  @ManyToOne(() => AnalysisRun, (run) => run.candidates)
  @JoinColumn({ name: 'run_id' })
  run!: AnalysisRun;

  @ManyToOne(() => IpoCandidate)
  @JoinColumn({ name: 'candidate_id' })
  candidate!: IpoCandidate;

  @ManyToOne(() => Prediction)
  @JoinColumn({ name: 'prediction_id' })
  prediction!: Prediction;
}
