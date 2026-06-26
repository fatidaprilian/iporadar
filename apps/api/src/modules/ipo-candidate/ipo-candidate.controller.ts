import {
  Controller,
  Get,
  Post,
  Put,
  Param,
  Body,
  Query,
  ParseUUIDPipe,
} from '@nestjs/common';
import { IpoCandidateService } from './ipo-candidate.service.js';
import {
  CreateIpoCandidateDto,
  UpdateIpoCandidateDto,
  ListCandidatesQueryDto,
} from './ipo-candidate.dto.js';

@Controller('ipo-candidates')
export class IpoCandidateController {
  constructor(private readonly candidateService: IpoCandidateService) {}

  @Post()
  create(@Body() dto: CreateIpoCandidateDto) {
    return this.candidateService.create(dto);
  }

  @Get()
  findAll(@Query() query: ListCandidatesQueryDto) {
    return this.candidateService.findAll(query);
  }

  @Get(':id')
  findOne(@Param('id', ParseUUIDPipe) id: string) {
    return this.candidateService.findOne(id);
  }

  @Put(':id')
  update(
    @Param('id', ParseUUIDPipe) id: string,
    @Body() dto: UpdateIpoCandidateDto,
  ) {
    return this.candidateService.update(id, dto);
  }
}
