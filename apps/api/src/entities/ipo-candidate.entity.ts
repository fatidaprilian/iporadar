import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  UpdateDateColumn,
  OneToOne,
  OneToMany,
  Index,
  VersionColumn,
} from 'typeorm';
import { Fundamental } from './fundamental.entity.js';
import { PriceData } from './price-data.entity.js';
import { NewsArticle } from './news-article.entity.js';
import { Prediction } from './prediction.entity.js';

export enum CandidateStatus {
  UPCOMING = 'upcoming',
  LISTED = 'listed',
  DELISTED = 'delisted',
}

@Entity('ipo_candidate')
export class IpoCandidate {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'varchar', unique: true })
  @Index('idx_candidate_ticker', { unique: true })
  ticker!: string;

  @Column({ type: 'varchar', name: 'company_name' })
  companyName!: string;

  @Column({ type: 'varchar' })
  @Index('idx_candidate_sector')
  sector!: string;

  @Column({ type: 'date', name: 'listing_date' })
  @Index('idx_candidate_listing_date')
  listingDate!: string;

  /** Offer price in IDR (minor units). IDR has no subunits so this equals the nominal value. */
  @Column({ type: 'integer', name: 'offer_price_idr' })
  offerPriceIdr!: number;

  @Column({ type: 'bigint', name: 'share_count' })
  shareCount!: string; // bigint returned as string by pg driver

  @Column({ type: 'varchar' })
  underwriter!: string;

  @Column({ type: 'smallint', name: 'underwriter_tier' })
  underwriterTier!: number;

  @Column({ type: 'varchar', default: CandidateStatus.UPCOMING })
  @Index('idx_candidate_status')
  status!: CandidateStatus;

  @VersionColumn()
  version!: number;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt!: Date;

  @UpdateDateColumn({ type: 'timestamptz', name: 'updated_at' })
  updatedAt!: Date;

  // Relations
  @OneToOne(() => Fundamental, (f) => f.candidate, { cascade: true })
  fundamental?: Fundamental;

  @OneToMany(() => PriceData, (p) => p.candidate)
  priceData?: PriceData[];

  @OneToMany(() => NewsArticle, (n) => n.candidate)
  newsArticles?: NewsArticle[];

  @OneToMany(() => Prediction, (p) => p.candidate)
  predictions?: Prediction[];
}
