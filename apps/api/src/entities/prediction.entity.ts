import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
  Unique,
} from 'typeorm';
import { IpoCandidate } from './ipo-candidate.entity.js';

@Entity('prediction')
@Unique('idx_prediction_candidate_version', ['candidateId', 'modelVersion'])
export class Prediction {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'uuid', name: 'candidate_id' })
  @Index('idx_prediction_candidate')
  candidateId!: string;

  @Column({ type: 'varchar', name: 'model_version' })
  modelVersion!: string;

  @Column({
    type: 'decimal',
    precision: 6,
    scale: 4,
    name: 'layer1_probability',
    nullable: true,
  })
  layer1Probability!: string | null;

  @Column({ type: 'varchar', name: 'layer1_label', nullable: true })
  layer1Label!: string | null;

  @Column({ type: 'jsonb', name: 'layer1_feature_importance', nullable: true })
  layer1FeatureImportance!: Record<string, number> | null;

  @Column({
    type: 'decimal',
    precision: 6,
    scale: 4,
    name: 'layer2_probability',
    nullable: true,
  })
  layer2Probability!: string | null;

  @Column({ type: 'varchar', name: 'layer2_label', nullable: true })
  layer2Label!: string | null;

  @Column({ type: 'jsonb', name: 'layer2_feature_importance', nullable: true })
  layer2FeatureImportance!: Record<string, number> | null;

  @Column({
    type: 'decimal',
    precision: 5,
    scale: 3,
    name: 'sentiment_score',
    nullable: true,
  })
  sentimentScore!: string | null;

  @Column({
    type: 'decimal',
    precision: 5,
    scale: 3,
    name: 'sentiment_magnitude',
    nullable: true,
  })
  sentimentMagnitude!: string | null;

  @Column({ type: 'integer', name: 'news_count', nullable: true })
  newsCount!: number | null;

  @Column({
    type: 'decimal',
    precision: 6,
    scale: 4,
    name: 'composite_score',
    nullable: true,
  })
  compositeScore!: string | null;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt!: Date;

  // Relations
  @ManyToOne(() => IpoCandidate, (c) => c.predictions)
  @JoinColumn({ name: 'candidate_id' })
  candidate!: IpoCandidate;
}
