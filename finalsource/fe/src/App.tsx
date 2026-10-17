import { AppRouter } from './router/AppRouter';
import { AuthProvider } from './context/AuthContext';

export function App() {
  return (
    <AuthProvider>
      <AppRouter />
    </AuthProvider>
  );
}
