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

@Entity('price_data')
@Unique('idx_price_candidate_date', ['candidateId', 'tradeDate'])
export class PriceData {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'uuid', name: 'candidate_id' })
  candidateId!: string;

  @Column({ type: 'date', name: 'trade_date' })
  @Index('idx_price_trade_date')
  tradeDate!: string;

  /** OHLCV prices in IDR (integer, no float per DATA-001). */
  @Column({ type: 'integer', name: 'open_idr' })
  openIdr!: number;

  @Column({ type: 'integer', name: 'high_idr' })
  highIdr!: number;

  @Column({ type: 'integer', name: 'low_idr' })
  lowIdr!: number;

  @Column({ type: 'integer', name: 'close_idr' })
  closeIdr!: number;

  @Column({ type: 'bigint' })
  volume!: string;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt!: Date;

  // Relations
  @ManyToOne(() => IpoCandidate, (c) => c.priceData)
  @JoinColumn({ name: 'candidate_id' })
  candidate!: IpoCandidate;
}
