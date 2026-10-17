import { ArgumentsHost, Catch, ExceptionFilter, HttpException, HttpStatus, Logger } from '@nestjs/common';
import type { Request, Response } from 'express';

@Catch()
export class HttpExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(HttpExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const context = host.switchToHttp();
    const response = context.getResponse<Response>();
    const request = context.getRequest<Request>();
    const status = exception instanceof HttpException ? exception.getStatus() : HttpStatus.INTERNAL_SERVER_ERROR;
    if (request.path === '/api/v1/accounts' && status === 401) {
      this.logger.warn('Account list authentication rejected');
    }
    if (request.method === 'DELETE' && /^\/api\/v1\/accounts\/[^/]+$/.test(request.path)) {
      this.logger.warn(`Account deletion request rejected with status ${status}`);
    }
    if (request.path === '/api/auth/register' && this.isValidationFailure(exception)) {
      this.logger.warn('Registration request rejected by DTO validation');
    }
    if (request.path === '/api/v1/transactions') {
      this.logger.warn(`Transaction request rejected with status ${status}`);
    }
    if (request.path === '/api/v1/expenses/summary') {
      this.logger.warn(`Expense summary request rejected with status ${status}`);
    }
    if (request.path === '/api/v1/expenses/breakdown') {
      this.logger.warn(`Expense breakdown request rejected with status ${status}`);
    }
    if (/^\/api\/v1\/goals(?:\/[^/]+)?$/.test(request.path)) {
      this.logger.warn(`Goals request rejected with status ${status}`);
    }
    if (request.path === '/api/v1/savings/summary') {
      this.logger.warn(`Savings summary request rejected with status ${status}`);
    }
    const message = request.method === 'POST' && request.path === '/api/v1/transactions' && status === 400
      ? 'Invalid or missing transaction data'
      : this.safeMessage(exception, status);
    response.status(status).json({ success: false, statusCode: status, message, timestamp: new Date().toISOString(), path: request.url });
  }

  private isValidationFailure(exception: unknown): boolean {
    if (!(exception instanceof HttpException) || exception.getStatus() !== 400) return false;
    const body = exception.getResponse();
    return typeof body === 'object' && body !== null && 'message' in body && Array.isArray(body.message);
  }

  private safeMessage(exception: unknown, status: number): string | string[] {
    if (!(exception instanceof HttpException)) return 'Internal server error';
    const body = exception.getResponse();
    if (typeof body === 'string') return body;
    if (typeof body === 'object' && body !== null && 'message' in body) {
      const message = body.message;
      if (typeof message === 'string' || (Array.isArray(message) && message.every((item) => typeof item === 'string'))) return message;
    }
    return status >= 500 ? 'Internal server error' : 'Request failed';
  }
}
