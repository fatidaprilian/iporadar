import {
  Entity,
  PrimaryGeneratedColumn,
  Column,
  CreateDateColumn,
  ManyToOne,
  JoinColumn,
  Index,
} from 'typeorm';
import { IpoCandidate } from './ipo-candidate.entity.js';

export enum SentimentLabel {
  POSITIVE = 'positive',
  NEGATIVE = 'negative',
  NEUTRAL = 'neutral',
}

@Entity('news_article')
export class NewsArticle {
  @PrimaryGeneratedColumn('uuid')
  id!: string;

  @Column({ type: 'uuid', name: 'candidate_id' })
  @Index('idx_news_candidate')
  candidateId!: string;

  @Column({ type: 'varchar' })
  title!: string;

  @Column({ type: 'varchar' })
  source!: string;

  @Column({ type: 'varchar', unique: true })
  @Index('idx_news_url', { unique: true })
  url!: string;

  @Column({ type: 'date', name: 'published_date' })
  @Index('idx_news_published')
  publishedDate!: string;

  /** Sentiment score from XLM-RoBERTa: -1.0 to 1.0. Null until ML service processes it. */
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

  @Column({ type: 'varchar', name: 'sentiment_label', nullable: true })
  sentimentLabel!: SentimentLabel | null;

  @Column({ type: 'timestamptz', name: 'scraped_at' })
  scrapedAt!: Date;

  @CreateDateColumn({ type: 'timestamptz', name: 'created_at' })
  createdAt!: Date;

  // Relations
  @ManyToOne(() => IpoCandidate, (c) => c.newsArticles)
  @JoinColumn({ name: 'candidate_id' })
  candidate!: IpoCandidate;
}
