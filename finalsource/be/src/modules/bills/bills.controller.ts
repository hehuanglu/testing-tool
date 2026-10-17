import { Controller, Get, Header, Req, UseGuards } from '@nestjs/common';
import { ApiBearerAuth, ApiOkResponse, ApiTags } from '@nestjs/swagger';
import { ResponseMessage } from '../../common/decorators/response-message.decorator';
import type { Request } from 'express';
import { JwtAuthGuard } from '../auth/jwt-auth.guard';
import { BillsService } from './bills.service';
import { BillsPayloadDto } from './dto/bill-response.dto';

@ApiTags('bills')
@ApiBearerAuth()
@UseGuards(JwtAuthGuard)
@Controller('v1/bills')
export class BillsController {
  constructor(private readonly bills: BillsService) {}

  @Get()
  @Header('Cache-Control', 'no-store')
  @ResponseMessage('Bills fetched successfully')
  @ApiOkResponse({ type: BillsPayloadDto })
  upcoming(@Req() request: Request & { user: { userId: number } }): Promise<BillsPayloadDto> {
    return this.bills.upcoming(request.user.userId);
  }
}
