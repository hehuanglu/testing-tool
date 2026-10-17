import { LoginForm } from '../components/auth/LoginForm';
import { useLocation } from 'react-router-dom';

export function LoginPage() {
  const location = useLocation();
  const state: unknown = location.state;
  const showSessionMessage = typeof state === 'object' && state !== null && 'sessionMessage' in state && state.sessionMessage === 'Please log in again.';
  return (
    <main className="min-h-screen bg-[#f4f5f7] text-[#191d23]">
      <div className="mx-auto flex w-full max-w-[400px] flex-col items-center px-4 pb-16 pt-20 sm:px-0 lg:pt-40">
        <div aria-label="FINEbank.IO" className="h-8 whitespace-nowrap font-['Poppins',sans-serif] text-[40px] leading-8 tracking-[3.2px] text-[#299d91]">
          <span className="font-extrabold">FINE</span><span className="font-medium">bank.</span><span className="font-extrabold">IO</span>
        </div>
        {showSessionMessage && <p role="alert" className="mt-6 text-sm text-[#666]">Please log in again.</p>}
        <LoginForm />
      </div>
    </main>
  );
}
