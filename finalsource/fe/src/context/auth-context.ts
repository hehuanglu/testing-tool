import { createContext, useContext } from 'react';
import type { AuthenticatedUser } from '../api/auth';

export interface AuthContextValue {
  user: AuthenticatedUser | null;
  isAuthenticated: boolean;
  completeLogin: (user: AuthenticatedUser, accessToken: string, rememberMe: boolean) => void;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}
