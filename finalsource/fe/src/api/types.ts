export interface ApiSuccess<T> {
  success: true;
  message: string;
  data: T;
}

export interface ApiError {
  success: false;
  message: string | string[];
  statusCode: number;
  timestamp: string;
  path: string;
}
