import { Link } from 'react-router-dom';

export function GoalDestinationUnavailablePage() {
  return <main className="flex min-h-screen items-center justify-center bg-[#f4f5f7] p-6"><section className="max-w-lg rounded-2xl bg-white p-10 text-center shadow-[0_18px_35px_rgba(33,43,54,0.10)]"><h1 className="text-2xl font-semibold text-[#333]">Goal editing is handled by its dedicated use case</h1><p className="mt-4 text-[#777]">UC-013 provides navigation only and does not introduce goal mutation behavior.</p><Link to="/goals" className="mt-7 inline-block rounded-md border border-[#299d91] px-5 py-3 font-medium text-[#299d91] focus:outline-none focus:ring-2 focus:ring-[#299d91]">Back to Goals</Link></section></main>;
}
