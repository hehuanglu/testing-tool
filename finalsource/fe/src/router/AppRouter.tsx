import { createBrowserRouter, Navigate, RouterProvider } from 'react-router-dom';
import { AppShell } from '../components/layout/AppShell';
import { BillsLayout } from '../components/layout/BillsLayout';
import { HomePage } from '../pages/HomePage';
import { NotFoundPage } from '../pages/NotFoundPage';
import { LoginPage } from '../pages/LoginPage';
import { RegistrationPage } from '../pages/RegistrationPage';
import { TransactionsPage } from '../pages/TransactionsPage';
import { AddTransactionPage } from '../pages/AddTransactionPage';
import { AccountListPage } from '../pages/AccountListPage';
import { AddAccountPage } from '../pages/AddAccountPage';
import { AccountDetailPage } from '../pages/AccountDetailPage';
import { ExpenseSummaryPage } from '../pages/ExpenseSummaryPage';
import { BillsPage } from '../pages/BillsPage';
import { NewBillPage } from '../pages/NewBillPage';
import { GoalsPage } from '../pages/GoalsPage';
import { GoalDestinationUnavailablePage } from '../pages/GoalDestinationUnavailablePage';
import { useAuth } from '../context/auth-context';

function ProtectedTransactionsPage() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <TransactionsPage /> : <Navigate to="/login" replace />;
}

function ProtectedAddTransactionPage() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <AddTransactionPage /> : <Navigate to="/login" replace />;
}

function ProtectedAccountListPage() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <AccountListPage /> : <Navigate to="/login" replace state={{ sessionMessage: 'Please log in again.' }} />;
}

function ProtectedAddAccountPage() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <AddAccountPage /> : <Navigate to="/login" replace state={{ sessionMessage: 'Please log in again.' }} />;
}

function ProtectedAccountDetailPage() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <AccountDetailPage /> : <Navigate to="/login" replace state={{ sessionMessage: 'Please log in again.' }} />;
}

function ProtectedExpenseSummaryPage() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <ExpenseSummaryPage /> : <Navigate to="/login" replace state={{ sessionMessage: 'Please log in again.' }} />;
}

function ProtectedBillsLayout() {
  const { isAuthenticated } = useAuth();
  return isAuthenticated ? <BillsLayout /> : <Navigate to="/login" replace state={{ sessionMessage: 'Please log in again.' }} />;
}

function ProtectedGoalsPage({ createMode = false }: { readonly createMode?: boolean }) { const { isAuthenticated } = useAuth(); return isAuthenticated ? <GoalsPage createMode={createMode} /> : <Navigate to="/login" replace state={{ sessionMessage: 'Please log in again.' }} />; }
function ProtectedGoalDestinationPage() { const { isAuthenticated } = useAuth(); return isAuthenticated ? <GoalDestinationUnavailablePage /> : <Navigate to="/login" replace state={{ sessionMessage: 'Please log in again.' }} />; }

const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegistrationPage /> },
  { path: '/transactions', element: <ProtectedTransactionsPage /> },
  { path: '/transactions/new', element: <ProtectedAddTransactionPage /> },
  { path: '/accounts', element: <ProtectedAccountListPage /> },
  { path: '/accounts/:id', element: <ProtectedAccountDetailPage /> },
  { path: '/accounts/new', element: <ProtectedAddAccountPage /> },
  { path: '/expenses', element: <ProtectedExpenseSummaryPage /> },
  {
    path: '/bills',
    element: <ProtectedBillsLayout />,
    children: [
      { index: true, element: <BillsPage /> },
      { path: 'new', element: <NewBillPage /> },
    ],
  },
  { path: '/goals', element: <ProtectedGoalsPage /> },
  { path: '/goals/new', element: <ProtectedGoalsPage createMode /> },
  { path: '/goals/:goalId/edit', element: <ProtectedGoalDestinationPage /> },
  {
    path: '/',
    element: <AppShell />,
    children: [
      { index: true, element: <HomePage /> },
      { path: '*', element: <NotFoundPage /> },
    ],
  },
]);

export function AppRouter() {
  return <RouterProvider router={router} />;
}
