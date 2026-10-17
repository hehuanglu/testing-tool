import { useMemo, useState, type PropsWithChildren } from 'react';
import type { AuthenticatedUser } from '../api/auth';
import { AuthContext, type AuthContextValue } from './auth-context';

const tokenKey = 'finebank.accessToken';

function existingToken(): string | null {
  return localStorage.getItem(tokenKey) ?? sessionStorage.getItem(tokenKey);
}

export function AuthProvider({ children }: PropsWithChildren) {
  const [user, setUser] = useState<AuthenticatedUser | null>(null);
  const [token, setToken] = useState<string | null>(() => existingToken());

  const value = useMemo<AuthContextValue>(() => ({
    user,
    isAuthenticated: token !== null,
    completeLogin: (authenticatedUser, accessToken, rememberMe) => {
      localStorage.removeItem(tokenKey);
      sessionStorage.removeItem(tokenKey);
      const storage = rememberMe ? localStorage : sessionStorage;
      storage.setItem(tokenKey, accessToken);
      setToken(accessToken);
      setUser(authenticatedUser);
    },
    logout: () => {
      localStorage.removeItem(tokenKey);
      sessionStorage.removeItem(tokenKey);
      setToken(null);
      setUser(null);
    },
  }), [token, user]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
