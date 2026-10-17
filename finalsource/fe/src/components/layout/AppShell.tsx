import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../../context/auth-context';

export function AppShell() {
  const { isAuthenticated } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-7xl px-4 py-4 sm:px-6 lg:px-8">
          <span className="text-lg font-semibold">Security vibe coding</span>
        </div>
      </header>
      <div className={isAuthenticated ? 'mx-auto grid max-w-7xl gap-6 px-4 py-8 sm:px-6 lg:grid-cols-[220px_1fr] lg:px-8' : 'mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8'}>
        {isAuthenticated && (
          <aside className="rounded-xl bg-[#191919] p-4 text-white" aria-label="Application sidebar">
            <nav aria-label="Primary">
              <NavLink className="mb-3 flex rounded-md px-4 py-3 font-semibold focus:outline-none focus:ring-2 focus:ring-white" to="/accounts">
                Balances
              </NavLink>
              <NavLink className="flex rounded-md bg-[#299d91] px-4 py-3 font-semibold focus:outline-none focus:ring-2 focus:ring-white" to="/transactions">
                Transactions
              </NavLink>
            </nav>
          </aside>
        )}
        <main>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
