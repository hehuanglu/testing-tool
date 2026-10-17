import { CallHandler, ExecutionContext, Injectable, NestInterceptor } from '@nestjs/common';
import { Observable, map } from 'rxjs';
import { Reflector } from '@nestjs/core';
import { RESPONSE_MESSAGE } from '../common/decorators/response-message.decorator';

export interface ApiResponse<T> { success: true; message: string; data: T }

@Injectable()
export class ResponseInterceptor<T> implements NestInterceptor<T, ApiResponse<T>> {
  constructor(private readonly reflector: Reflector) {}

  intercept(context: ExecutionContext, next: CallHandler<T>): Observable<ApiResponse<T>> {
    const message = this.reflector.getAllAndOverride<string>(RESPONSE_MESSAGE, [context.getHandler(), context.getClass()]) ?? 'Request completed successfully';
    return next.handle().pipe(map((data) => ({ success: true, message, data })));
  }
}
