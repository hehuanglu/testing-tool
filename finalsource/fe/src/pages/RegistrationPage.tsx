import { SignUpForm } from '../components/auth/SignUpForm';

export function RegistrationPage() {
  return (
    <main className="min-h-screen bg-[#f4f5f7] text-[#191d23]">
      <div className="mx-auto flex w-full max-w-[400px] flex-col items-center px-4 pb-16 pt-12 sm:px-0 lg:pt-20">
        <div aria-label="FINEbank.IO" className="h-8 whitespace-nowrap font-['Poppins',sans-serif] text-[40px] leading-8 tracking-[3.2px] text-[#299d91]">
          <span className="font-extrabold">FINE</span><span className="font-medium">bank.</span><span className="font-extrabold">IO</span>
        </div>
        <h1 className="mt-10 text-[28px] font-semibold leading-9">Create an account</h1>
        <SignUpForm />
      </div>
    </main>
  );
}
