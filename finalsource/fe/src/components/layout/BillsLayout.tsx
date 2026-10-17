import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/auth-context';
import '../../bills.css';

export function BillsLayout() {
  const { logout } = useAuth();
  const navigate = useNavigate();
  const navigation = ['Overview', 'Balances', 'Transactions', 'Bills', 'Expenses', 'Goals', 'Settings'];

  return (
    <div className="financial-shell">
      <aside className="financial-sidebar">
        <div className="bank-wordmark" role="img" aria-label="FINEbank.IO" />
        <nav aria-label="Main navigation">
          {navigation.map((label, index) => {
            const contents = <><span className={`nav-icon nav-icon-${index}`} aria-hidden="true" /><span>{label}</span></>;
            if (label === 'Bills' || label === 'Overview') {
              return <NavLink key={label} to={label === 'Bills' ? '/bills' : '/'} end={label === 'Overview'} className={({ isActive }) => `financial-nav${isActive ? ' active' : ''}`}>{contents}</NavLink>;
            }
            return <button key={label} type="button" className="financial-nav" disabled aria-label={`${label} — unavailable in this view`}>{contents}</button>;
          })}
        </nav>
        <div className="sidebar-bottom">
          <button className="logout-button" type="button" onClick={() => { logout(); navigate('/login'); }}><span className="logout-icon" aria-hidden="true" />Logout</button>
          <div className="sidebar-profile"><span className="profile-avatar" aria-hidden="true" /><div><strong>Tanzir Rahman</strong><span>View profile</span></div><button type="button" disabled aria-label="Profile options unavailable">⋮</button></div>
        </div>
      </aside>
      <div className="financial-workspace">
        <header className="financial-header"><span className="header-date"><span aria-hidden="true">»</span> May 19, 2023</span><div className="header-tools"><span className="notification-icon" role="img" aria-label="Notifications" /><div className="visual-search" aria-label="Search — visual preview only"><span>Search here</span><span className="search-icon" aria-hidden="true" /></div></div></header>
        <main className="financial-main"><Outlet /></main>
      </div>
    </div>
  );
}
