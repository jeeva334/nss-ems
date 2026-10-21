import { CheckCircle2, AlertTriangle, Loader2 } from "lucide-react";
import { getReadiness } from "../services/healthService";
import { useAsync } from "../hooks/useAsync";

export default function DashboardPage() {
  const { loading, data, error, retry } = useAsync(getReadiness);
  return (
    <section>
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="text-slate-600 mt-1">Overview of the portal.</p>
      <div className="mt-6 max-w-md rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        <h2 className="font-medium">System status</h2>
        {loading && (
          <p className="mt-3 flex items-center gap-2 text-slate-600">
            <Loader2 className="animate-spin" size={16} /> Checking backend…
          </p>
        )}
        {data && (
          <p className="mt-3 flex items-center gap-2 text-green-700">
            <CheckCircle2 size={16} /> API and database are reachable.
          </p>
        )}
        {error && (
          <div className="mt-3 text-red-700">
            <p className="flex items-center gap-2">
              <AlertTriangle size={16} /> {error.message}
            </p>
            <button onClick={retry} className="mt-3 rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white hover:bg-blue-700">
              Retry
            </button>
          </div>
        )}
      </div>
    </section>
  );
}
