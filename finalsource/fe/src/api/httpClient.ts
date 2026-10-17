import axios from 'axios';

const configuredBaseUrl = import.meta.env.VITE_API_BASE_URL?.trim();

export const httpClient = axios.create({
  baseURL: configuredBaseUrl || '/api',
  headers: { Accept: 'application/json' },
  timeout: 15_000,
});

httpClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('finebank.accessToken') ?? sessionStorage.getItem('finebank.accessToken');
  if (token) config.headers.set('Authorization', `Bearer ${token}`);
  return config;
});

httpClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => Promise.reject(error),
);
