import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  OneToMany,
  OneToOne,
  Index,
} from 'typeorm';
import { AnalysisCandidate } from './analysis-candidate.entity.js';
import { AnalysisResult } from './analysis-result.entity.js';

export enum RunStatus {
  QUEUED = 'queued',
  PROCESSING = 'processing',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

export enum TriggerType {
  MANUAL = 'manual',
  SCHEDULED = 'scheduled',
}

@Entity('analysis_run')
export class AnalysisRun {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'varchar', default: RunStatus.QUEUED })
  @Index('idx_run_status')
  status!: RunStatus;

  @Column({ type: 'integer', name: 'top_n', default: 5 })
  topN!: number;

  @Column({ type: 'varchar', name: 'trigger_type' })
  triggerType!: TriggerType;

  @Column({ type: 'timestamptz', name: 'started_at', nullable: true })
  startedAt!: Date | null;

  @Column({ type: 'timestamptz', name: 'completed_at', nullable: true })
  completedAt!: Date | null;

  @Column({ type: 'varchar', name: 'error_message', nullable: true })
  errorMessage!: string | null;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  @Index('idx_run_created')
  createdAt!: Date;

  // Relations
  @OneToMany(() => AnalysisCandidate, (ac) => ac.run, { cascade: true })
  candidates?: AnalysisCandidate[];

  @OneToOne(() => AnalysisResult, (ar) => ar.run, { cascade: true })
  result?: AnalysisResult;
}
