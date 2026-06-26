import { Controller, Post, Get, Body } from '@nestjs/common';
import { ScraperService } from './scraper.service.js';
import { RunScraperDto } from './scraper.dto.js';

@Controller('scraper')
export class ScraperController {
  constructor(private readonly scraperService: ScraperService) {}

  @Post('run')
  run(@Body() dto: RunScraperDto) {
    return this.scraperService.run(dto);
  }

  @Get('status')
  status() {
    return this.scraperService.getStatus();
  }
}
