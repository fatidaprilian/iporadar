import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  OneToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { IpoCandidate } from './ipo-candidate.entity.js';

@Entity('fundamental')
export class Fundamental {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'uuid', name: 'candidate_id' })
  @Index('idx_fundamental_candidate', { unique: true })
  candidateId!: string;

  @Column({
    type: 'decimal',
    precision: 10,
    scale: 2,
    name: 'pe_ratio',
    nullable: true,
  })
  peRatio!: string | null;

  @Column({
    type: 'decimal',
    precision: 10,
    scale: 2,
    name: 'pb_ratio',
    nullable: true,
  })
  pbRatio!: string | null;

  @Column({ type: 'decimal', precision: 8, scale: 4, nullable: true })
  roe!: string | null;

  @Column({
    type: 'decimal',
    precision: 10,
    scale: 4,
    name: 'debt_to_equity',
    nullable: true,
  })
  debtToEquity!: string | null;

  /** Total assets in IDR (integer, no float per DATA-001). */
  @Column({ type: 'bigint', name: 'total_assets_idr', nullable: true })
  totalAssetsIdr!: string | null;

  @Column({ type: 'bigint', name: 'revenue_idr', nullable: true })
  revenueIdr!: string | null;

  @Column({ type: 'bigint', name: 'net_income_idr', nullable: true })
  netIncomeIdr!: string | null;

  @Column({
    type: 'decimal',
    precision: 8,
    scale: 4,
    name: 'revenue_growth_yoy',
    nullable: true,
  })
  revenueGrowthYoy!: string | null;

  @Column({
    type: 'decimal',
    precision: 10,
    scale: 2,
    name: 'sector_avg_pe',
    nullable: true,
  })
  sectorAvgPe!: string | null;

  @Column({
    type: 'decimal',
    precision: 10,
    scale: 2,
    name: 'sector_avg_pb',
    nullable: true,
  })
  sectorAvgPb!: string | null;

  @Column({ type: 'timestamptz', name: 'report_date', nullable: true })
  reportDate!: Date | null;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt!: Date;

  // Relations
  @OneToOne(() => IpoCandidate, (c) => c.fundamental)
  @JoinColumn({ name: 'candidate_id' })
  candidate!: IpoCandidate;
}
