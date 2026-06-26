import { Injectable, NotFoundException } from '@nestjs/common';
import { InjectRepository } from '@nestjs/typeorm';
import { Repository, FindOptionsWhere } from 'typeorm';
import { IpoCandidate, CandidateStatus } from '../../entities/index.js';
import {
  CreateIpoCandidateDto,
  UpdateIpoCandidateDto,
  ListCandidatesQueryDto,
} from './ipo-candidate.dto.js';

@Injectable()
export class IpoCandidateService {
  constructor(
    @InjectRepository(IpoCandidate)
    private readonly candidateRepo: Repository<IpoCandidate>,
  ) {}

  async create(dto: CreateIpoCandidateDto): Promise<IpoCandidate> {
    const candidate = this.candidateRepo.create({
      ...dto,
      status: dto.status ?? CandidateStatus.UPCOMING,
    });
    return this.candidateRepo.save(candidate);
  }

  async findAll(query: ListCandidatesQueryDto) {
    const where: FindOptionsWhere<IpoCandidate> = {};
    if (query.status) where.status = query.status;
    if (query.sector) where.sector = query.sector;

    const page = query.page ?? 1;
    const limit = query.limit ?? 20;

    const [data, total] = await this.candidateRepo.findAndCount({
      where,
      relations: { fundamental: true },
      order: { listingDate: 'DESC' },
      skip: (page - 1) * limit,
      take: limit,
    });

    return {
      data,
      meta: {
        page,
        limit,
        total,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  async findOne(id: string): Promise<IpoCandidate> {
    const candidate = await this.candidateRepo.findOne({
      where: { id },
      relations: {
        fundamental: true,
        priceData: true,
        newsArticles: true,
        predictions: true,
      },
    });
    if (!candidate) {
      throw new NotFoundException('IPO candidate not found');
    }
    return candidate;
  }

  async findByTicker(ticker: string): Promise<IpoCandidate | null> {
    return this.candidateRepo.findOne({
      where: { ticker },
      relations: { fundamental: true },
    });
  }

  async update(id: string, dto: UpdateIpoCandidateDto): Promise<IpoCandidate> {
    const candidate = await this.findOne(id);
    Object.assign(candidate, dto);
    return this.candidateRepo.save(candidate);
  }

  async findUpcoming(): Promise<IpoCandidate[]> {
    return this.candidateRepo.find({
      where: { status: CandidateStatus.UPCOMING },
      relations: { fundamental: true },
      order: { listingDate: 'ASC' },
    });
  }

  async findRecentlyListed(daysSinceListing = 30): Promise<IpoCandidate[]> {
    const cutoff = new Date();
    cutoff.setDate(cutoff.getDate() - daysSinceListing);

    return this.candidateRepo
      .createQueryBuilder('c')
      .leftJoinAndSelect('c.fundamental', 'f')
      .where('c.status = :status', { status: CandidateStatus.LISTED })
      .andWhere('c.listing_date >= :cutoff', {
        cutoff: cutoff.toISOString().split('T')[0],
      })
      .orderBy('c.listing_date', 'DESC')
      .getMany();
  }
}
