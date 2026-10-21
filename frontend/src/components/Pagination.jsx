export default function Pagination({ page, pageSize, total, onChange }) {
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);
  const last = Math.max(1, Math.ceil(total / pageSize));
  const btn = "rounded-lg border border-slate-300 px-3 py-1.5 text-sm disabled:opacity-40";
  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 px-4 py-3 text-sm text-slate-600">
      <span>Showing {from}–{to} of {total}</span>
      <span className="flex gap-2">
        <button className={btn} disabled={page <= 1} onClick={() => onChange(page - 1)}>Previous</button>
        <button className={btn} disabled={page >= last} onClick={() => onChange(page + 1)}>Next</button>
      </span>
    </nav>
  );
}
