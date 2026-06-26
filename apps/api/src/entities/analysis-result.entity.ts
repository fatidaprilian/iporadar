import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  OneToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { AnalysisRun } from './analysis-run.entity.js';

@Entity('analysis_result')
export class AnalysisResult {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'uuid', name: 'run_id' })
  @Index('idx_result_run', { unique: true })
  runId!: string;

  @Column({ type: 'integer', name: 'candidate_count' })
  candidateCount!: number;

  @Column({ type: 'text' })
  prompt!: string;

  /** Denormalized summary for quick dashboard display without joins. */
  @Column({ type: 'jsonb', name: 'top_candidates_summary' })
  topCandidatesSummary!: Record<string, unknown>[];

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt!: Date;

  // Relations
  @OneToOne(() => AnalysisRun, (run) => run.result)
  @JoinColumn({ name: 'run_id' })
  run!: AnalysisRun;
}
