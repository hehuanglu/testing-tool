import { Link } from 'react-router-dom';

export function NotFoundPage() {
  return (
    <section aria-labelledby="not-found-heading">
      <h1 id="not-found-heading" className="text-2xl font-semibold">Không tìm thấy trang</h1>
      <Link className="mt-4 inline-block text-blue-700 underline" to="/">Về trang chính</Link>
    </section>
  );
}
