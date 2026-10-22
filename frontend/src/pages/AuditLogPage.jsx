import { useCallback } from "react";
import { useSearchParams } from "react-router-dom";
import { AlertTriangle, Loader2, ScrollText } from "lucide-react";
import { listAuditLogs } from "../services/auditService";
import { useAsync } from "../hooks/useAsync";
import Pagination from "../components/Pagination";

const PAGE_SIZE = 25;
const CATEGORIES = [["", "All activity"], ["auth.", "Sign-in & activation"], ["user.", "Users"], ["invitation.", "Invitations"],
  ["client.", "Clients"], ["supervisor.", "Supervisor assignments"], ["admin.", "Admin setup"]];
const field = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm";
// Day boundaries in the viewer's local time, sent to the API as UTC instants.
const startOfDay = (d) => (d ? new Date(`${d}T00:00:00`).toISOString() : "");
const endOfDay = (d) => (d ? new Date(`${d}T23:59:59.999`).toISOString() : "");

export default function AuditLogPage() {
  const [params, setParams] = useSearchParams();
  const action = params.get("action") || "", from = params.get("from") || "", to = params.get("to") || "";
  const page = Number(params.get("page") || 1);
  const fetcher = useCallback(() => listAuditLogs({ action, date_from: startOfDay(from), date_to: endOfDay(to), page, page_size: PAGE_SIZE }),
    [action, from, to, page]);
  const { loading, data, error, retry } = useAsync(fetcher);

  const update = (patch) => {
    const next = new URLSearchParams(params);
    Object.entries({ page: 1, ...patch }).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next);
  };
  const keep = { action, from, to };

  return (
    <section>
      <h1 className="text-2xl font-semibold">Audit Log</h1>
      <p className="mt-1 text-slate-600">Security-sensitive and administrative actions. Secrets are never recorded.</p>
      <div className="mt-6 flex flex-wrap items-end gap-3">
        <div><label htmlFor="cat" className="block text-xs text-slate-500">Category</label>
          <select id="cat" className={field} value={action} onChange={(e) => update({ ...keep, action: e.target.value })}>
            {CATEGORIES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></div>
        <div><label htmlFor="from" className="block text-xs text-slate-500">From</label>
          <input id="from" type="date" className={field} value={from} max={to || undefined} onChange={(e) => update({ ...keep, from: e.target.value })} /></div>
        <div><label htmlFor="to" className="block text-xs text-slate-500">To</label>
          <input id="to" type="date" className={field} value={to} min={from || undefined} onChange={(e) => update({ ...keep, to: e.target.value })} /></div>
      </div>

      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading && <p className="flex items-center gap-2 p-6 text-slate-600"><Loader2 className="animate-spin" size={16} /> Loading audit log…</p>}
        {error && <div role="alert" className="p-6 text-red-700"><p className="flex items-center gap-2"><AlertTriangle size={16} /> {error.message}</p>
          <button onClick={retry} className="mt-3 rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white">Retry</button></div>}
        {data && data.items.length === 0 && <div className="p-10 text-center text-slate-600"><ScrollText className="mx-auto mb-2 text-slate-400" aria-hidden />No audit events match these filters.</div>}
        {data && data.items.length > 0 && (<>
          <div className="overflow-x-auto"><table className="w-full text-left text-sm">
            <thead className="bg-slate-50 text-slate-600"><tr>{["Time", "Actor", "Action", "Target", "Details"].map((h) => (
              <th key={h} scope="col" className="whitespace-nowrap px-4 py-3 font-medium">{h}</th>))}</tr></thead>
            <tbody className="divide-y divide-slate-100 align-top">{data.items.map((e) => (
              <tr key={e.id}>
                <td className="whitespace-nowrap px-4 py-3">{new Date(e.timestamp).toLocaleString()}</td>
                <td className="px-4 py-3">{e.actor ? `${e.actor.full_name} (${e.actor.employee_id})` : <span className="text-slate-500">System / anonymous</span>}</td>
                <td className="whitespace-nowrap px-4 py-3 font-medium">{e.action}</td>
                <td className="whitespace-nowrap px-4 py-3">{e.target_type ? `${e.target_type} #${e.target_id ?? "—"}` : "—"}</td>
                <td className="px-4 py-3">
                  <details><summary className="cursor-pointer text-blue-700">View</summary>
                    <pre className="mt-1 max-w-xs overflow-x-auto whitespace-pre-wrap text-xs text-slate-600">{JSON.stringify(e.metadata, null, 2)}</pre>
                    {e.correlation_id && <p className="mt-1 text-xs text-slate-500">Request ID: {e.correlation_id}</p>}</details>
                </td>
              </tr>))}</tbody></table></div>
          <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={(p) => update({ ...keep, page: p })} />
        </>)}
      </div>
    </section>
  );
}
