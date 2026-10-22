export const card = "rounded-2xl border border-slate-200 bg-white p-5 shadow-sm";
export const btn = "rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50";
export const primary = "rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700 disabled:opacity-50";
export const select = "rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-sm";

export const Row = ({ label, children }) => (
  <div className="flex justify-between gap-4 py-2 text-sm"><dt className="text-slate-500">{label}</dt><dd className="text-right font-medium">{children}</dd></div>
);

// Turns a 409 with affected Supervisors into a message the Admin can act on.
export function conflictMessage(e) {
  const sups = e?.details?.supervisors;
  if (sups?.length) return `${e.message} Affected: ${sups.map((s) => `${s.full_name} (${s.employee_id})`).join(", ")}.`;
  return e?.message || "Something went wrong.";
}
