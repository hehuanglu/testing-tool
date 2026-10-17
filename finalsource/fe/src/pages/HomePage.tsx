import { Link } from 'react-router-dom';
import { useAuth } from '../context/auth-context';

export function HomePage() {
  const { isAuthenticated, user, logout } = useAuth();

  return (
    <section aria-labelledby="starter-heading" className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
      <h1 id="starter-heading" className="text-2xl font-semibold">
        Application baseline is ready
      </h1>
      <p className="mt-2 max-w-2xl text-slate-600">
        {isAuthenticated ? `Welcome${user ? `, ${user.fullName}` : ''}.` : 'Sign in to access your financial dashboard.'}
      </p>
      {isAuthenticated ? (
        <button className="mt-6 rounded-md bg-[#299d91] px-4 py-2 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2" type="button" onClick={logout}>
          Logout
        </button>
      ) : (
        <Link className="mt-6 inline-flex rounded-md bg-[#299d91] px-4 py-2 font-semibold text-white focus:outline-none focus:ring-2 focus:ring-[#299d91] focus:ring-offset-2" to="/register">
          Register / Login
        </Link>
      )}
    </section>
  );
}
