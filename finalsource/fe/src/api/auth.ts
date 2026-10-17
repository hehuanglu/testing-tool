import axios from 'axios';
import { httpClient } from './httpClient';
import type { ApiError, ApiSuccess } from './types';

export interface LoginRequest {
  email: string;
  password: string;
}

export interface AuthenticatedUser {
  id: number;
  fullName: string;
  email: string;
}

export interface LoginResult {
  accessToken: string;
  user: AuthenticatedUser;
}

export interface RegisterRequest {
  fullName: string;
  email: string;
  password: string;
  'confirm Password': string;
}

export interface RegisterResult {
  token: string;
  user: AuthenticatedUser;
}

export interface SafeApiFailure {
  statusCode: number | null;
  message: string;
}

export async function login(payload: LoginRequest, signal?: AbortSignal): Promise<LoginResult> {
  const response = await httpClient.post<ApiSuccess<LoginResult>>('/auth/login', payload, { signal });
  return response.data.data;
}

export async function register(payload: RegisterRequest, signal?: AbortSignal): Promise<RegisterResult> {
  const response = await httpClient.post<ApiSuccess<RegisterResult>>('/auth/register', payload, { signal });
  return response.data.data;
}

export function toSafeApiFailure(error: unknown): SafeApiFailure {
  if (axios.isAxiosError<ApiError>(error)) {
    const body = error.response?.data;
    if (body && typeof body.message === 'string') return { statusCode: body.statusCode, message: body.message };
    return { statusCode: error.response?.status ?? null, message: 'Unable to sign in. Please try again.' };
  }
  return { statusCode: null, message: 'Unable to sign in. Please try again.' };
}
