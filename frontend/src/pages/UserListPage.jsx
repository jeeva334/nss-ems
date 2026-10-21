import { useCallback, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { AlertTriangle, Loader2, Plus, Search, Users } from "lucide-react";
import { listUsers } from "../services/userService";
import { useAsync } from "../hooks/useAsync";
import StatusBadge from "../components/StatusBadge";
import Pagination from "../components/Pagination";

const PAGE_SIZE = 20;
const select = "rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm";

export default function UserListPage() {
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "", role = params.get("role") || "", status = params.get("status") || "";
  const page = Number(params.get("page") || 1);
  const [text, setText] = useState(q);

  const fetcher = useCallback(() => listUsers({ q, role, status, page, page_size: PAGE_SIZE }), [q, role, status, page]);
  const { loading, data, error, retry } = useAsync(fetcher);

  const update = (patch) => {
    const next = new URLSearchParams(params);
    Object.entries({ page: 1, ...patch }).forEach(([k, v]) => (v ? next.set(k, v) : next.delete(k)));
    setParams(next);
  };

  return (
    <section>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold">User Management</h1>
          <p className="mt-1 text-slate-600">Create portal accounts and manage who can sign in.</p>
        </div>
        <button onClick={() => navigate("/users/new")}
          className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700">
          <Plus size={16} aria-hidden /> Create User
        </button>
      </div>

      <form role="search" onSubmit={(e) => { e.preventDefault(); update({ q: text.trim(), role, status }); }}
        className="mt-6 flex flex-wrap gap-3">
        <div className="relative min-w-[16rem] flex-1">
          <Search size={16} className="absolute left-3 top-3 text-slate-400" aria-hidden />
          <input aria-label="Search users" value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Search by Employee ID, name, email or mobile"
            className="w-full rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm" />
        </div>
        <select aria-label="Filter by role" className={select} value={role} onChange={(e) => update({ q, status, role: e.target.value })}>
          <option value="">All roles</option><option value="ADMIN">Admin</option>
          <option value="MANAGER">Manager</option><option value="SUPERVISOR">Supervisor</option>
        </select>
        <select aria-label="Filter by status" className={select} value={status} onChange={(e) => update({ q, role, status: e.target.value })}>
          <option value="">All statuses</option><option value="ACTIVE">Active</option>
          <option value="PENDING">Pending</option><option value="INACTIVE">Inactive</option>
        </select>
        <button type="submit" className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm">Search</button>
      </form>

      <div className="mt-4 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
        {loading && <p className="flex items-center gap-2 p-6 text-slate-600"><Loader2 className="animate-spin" size={16} /> Loading users…</p>}
        {error && (
          <div role="alert" className="p-6 text-red-700">
            <p className="flex items-center gap-2"><AlertTriangle size={16} /> {error.message}</p>
            <button onClick={retry} className="mt-3 rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white">Retry</button>
          </div>
        )}
        {data && data.items.length === 0 && (
          <div className="p-10 text-center text-slate-600">
            <Users className="mx-auto mb-2 text-slate-400" aria-hidden />
            {q || role || status ? "No users match these filters. Try clearing the search." : "No users yet. Create the first account to get started."}
          </div>
        )}
        {data && data.items.length > 0 && (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>{["Employee ID", "Full name", "Email", "Mobile", "Role", "Status", "Created", ""].map((h) => (
                    <th key={h} scope="col" className="whitespace-nowrap px-4 py-3 font-medium">{h || <span className="sr-only">Actions</span>}</th>))}</tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {data.items.map((u) => (
                    <tr key={u.id} className="hover:bg-slate-50">
                      <td className="whitespace-nowrap px-4 py-3 font-medium">{u.employee_id}</td>
                      <td className="px-4 py-3"><Link className="text-blue-700 hover:underline" to={`/users/${u.id}`}>{u.full_name}</Link></td>
                      <td className="px-4 py-3">{u.email}</td>
                      <td className="whitespace-nowrap px-4 py-3">{u.mobile_number}</td>
                      <td className="px-4 py-3">{u.role.charAt(0) + u.role.slice(1).toLowerCase()}</td>
                      <td className="px-4 py-3"><StatusBadge value={u.status} /></td>
                      <td className="whitespace-nowrap px-4 py-3">{new Date(u.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3"><Link className="text-blue-700 hover:underline" to={`/users/${u.id}`} aria-label={`View ${u.full_name}`}>View</Link></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <Pagination page={data.page} pageSize={data.page_size} total={data.total} onChange={(p) => update({ q, role, status, page: p })} />
          </>
        )}
      </div>
    </section>
  );
}
