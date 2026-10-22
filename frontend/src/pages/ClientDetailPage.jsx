import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";
import { editClientSchema } from "../schemas/clientSchemas";
import * as clientApi from "../services/clientService";
import * as userApi from "../services/userService";
import { useAsync } from "../hooks/useAsync";
import StatusBadge from "../components/StatusBadge";
import ConfirmDialog from "../components/ConfirmDialog";
import { btn, card, conflictMessage, primary, Row, select } from "../components/ui";

function EditForm({ client, onSaved, onCancel }) {
  const [err, setErr] = useState(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(editClientSchema),
    defaultValues: { client_name: client.client_name, address: client.address || "", contact_name: client.contact_name || "",
      contact_email: client.contact_email || "", contact_phone: client.contact_phone || "" },
  });
  const f = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm";
  return (
    <form onSubmit={handleSubmit(async (v) => { try { await clientApi.updateClient(client.id, v); onSaved(); } catch (e) { setErr(e.message); } })} noValidate className="space-y-3">
      {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
      {[["client_name", "Client name"], ["address", "Address"], ["contact_name", "Contact name"], ["contact_email", "Contact email"], ["contact_phone", "Contact phone"]].map(([n, l]) => (
        <div key={n}><label htmlFor={`c_${n}`} className="text-sm font-medium">{l}</label>
          <input id={`c_${n}`} className={f} {...register(n)} />{errors[n] && <p className="text-sm text-red-600">{errors[n].message}</p>}</div>))}
      <div className="flex gap-2"><button disabled={isSubmitting} className={primary}>Save changes</button><button type="button" onClick={onCancel} className={btn}>Cancel</button></div>
    </form>
  );
}

export default function ClientDetailPage() {
  const { id } = useParams();
  const fetcher = useCallback(() => clientApi.getClient(id), [id]);
  const { loading, data, error, retry } = useAsync(fetcher);
  const managers = useAsync(useCallback(() => userApi.listUsers({ role: "MANAGER", status: "ACTIVE", page_size: 100 }), []));
  const [notice, setNotice] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [pick, setPick] = useState("");

  const run = async (fn, okText) => {
    setBusy(true);
    try { await fn(); setNotice({ ok: true, text: okText }); setEditing(false); setPick(""); retry(); }
    catch (e) { setNotice({ ok: false, text: conflictMessage(e) }); }
    finally { setBusy(false); setConfirm(null); }
  };

  if (loading) return <p className="flex items-center gap-2 text-slate-600"><Loader2 className="animate-spin" size={16} /> Loading client…</p>;
  if (error) return <div role="alert" className="text-red-700"><p className="flex items-center gap-2"><AlertTriangle size={16} /> {error.status === 404 ? "This client does not exist." : error.message}</p>
    {error.status !== 404 && <button onClick={retry} className="mt-3 rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white">Retry</button>}</div>;

  const { client: c, supervisors } = data;
  const options = (managers.data?.items ?? []).filter((m) => m.id !== c.manager_id);
  const hasMgr = !!c.manager;
  return (
    <section className="max-w-4xl">
      <Link to="/clients" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:underline"><ArrowLeft size={14} /> Clients</Link>
      <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-semibold">{c.client_name}</h1><StatusBadge value={c.status} /></div>
      {notice && <p role={notice.ok ? "status" : "alert"} className={`mt-3 rounded-lg p-3 text-sm ${notice.ok ? "bg-green-50 text-green-800" : "bg-red-50 text-red-700"}`}>{notice.text}</p>}

      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <div className={card}>
          <h2 className="font-semibold">Details</h2>
          {editing ? <div className="mt-3"><EditForm client={c} onCancel={() => setEditing(false)} onSaved={() => { setNotice({ ok: true, text: "Client updated." }); setEditing(false); retry(); }} /></div> : (
            <dl className="mt-2 divide-y">
              <Row label="Client code">{c.client_code}</Row><Row label="Address">{c.address || "—"}</Row>
              <Row label="Contact">{c.contact_name || "—"}</Row><Row label="Email">{c.contact_email || "—"}</Row><Row label="Phone">{c.contact_phone || "—"}</Row>
            </dl>)}
          {!editing && <div className="mt-3 flex gap-2"><button className={btn} onClick={() => setEditing(true)}>Edit details</button>
            {c.status === "ACTIVE"
              ? <button className={`${btn} text-red-700`} disabled={busy} onClick={() => setConfirm({ kind: "deactivate" })}>Deactivate client</button>
              : <button className={btn} disabled={busy} onClick={() => run(() => clientApi.setClientStatus(c.id, "ACTIVE"), "Client reactivated.")}>Reactivate client</button>}</div>}
        </div>

        <div className={card}>
          <h2 className="font-semibold">Manager</h2>
          <dl className="mt-2 divide-y"><Row label="Current Manager">{c.manager
            ? <Link className="text-blue-700 hover:underline" to={`/users/${c.manager.id}`}>{`${c.manager.full_name} (${c.manager.employee_id})`}</Link> : "Unassigned"}</Row></dl>
          <div className="mt-3 flex flex-wrap items-center gap-2">
            <label htmlFor="mgr-pick" className="sr-only">Manager</label>
            <select id="mgr-pick" className={select} value={pick} onChange={(e) => setPick(e.target.value)} disabled={c.status !== "ACTIVE"}>
              <option value="">{hasMgr ? "Select new Manager…" : "Select Manager…"}</option>
              {options.map((m) => <option key={m.id} value={m.id}>{m.full_name} ({m.employee_id})</option>)}
            </select>
            {hasMgr
              ? <button className={primary} disabled={!pick || busy} onClick={() => setConfirm({ kind: "reassign", id: Number(pick) })}>Reassign Manager</button>
              : <button className={primary} disabled={!pick || busy || c.status !== "ACTIVE"} onClick={() => run(() => clientApi.putClientManager(c.id, Number(pick), false), "Manager assigned.")}>Assign Manager</button>}
            {hasMgr && <button className={btn} disabled={busy} onClick={() => setConfirm({ kind: "remove" })}>Remove Manager</button>}
          </div>
          {c.status !== "ACTIVE" && <p className="mt-2 text-xs text-slate-500">Inactive clients cannot be assigned to a Manager.</p>}
        </div>
      </div>

      <div className={`${card} mt-5`}>
        <h2 className="font-semibold">Assigned Supervisors</h2>
        {supervisors.length ? <ul className="mt-2 divide-y text-sm">{supervisors.map((s) => (
          <li key={s.id} className="py-2"><Link className="text-blue-700 hover:underline" to={`/users/${s.id}`}>{s.full_name}</Link> <span className="text-slate-500">{s.employee_id}</span></li>))}</ul>
          : <p className="mt-2 text-sm text-slate-600">No Supervisors assigned to this client.</p>}
      </div>

      {confirm?.kind === "deactivate" && <ConfirmDialog title="Deactivate this client?" confirmLabel="Deactivate" danger busy={busy}
        message="Blocked while Supervisors are assigned to it; you will be told who to move first." onCancel={() => setConfirm(null)}
        onConfirm={() => run(() => clientApi.setClientStatus(c.id, "INACTIVE"), "Client deactivated.")} />}
      {confirm?.kind === "reassign" && <ConfirmDialog title="Reassign this client to another Manager?" confirmLabel="Reassign" danger busy={busy}
        message={`${c.manager.full_name} will no longer manage ${c.client_name}. This is blocked while Supervisors are assigned to the client.`} onCancel={() => setConfirm(null)}
        onConfirm={() => run(() => clientApi.putClientManager(c.id, confirm.id, true), "Client reassigned.")} />}
      {confirm?.kind === "remove" && <ConfirmDialog title="Remove the Manager?" confirmLabel="Remove" danger busy={busy}
        message="The client will have no Manager. This is blocked while Supervisors are assigned to the client." onCancel={() => setConfirm(null)}
        onConfirm={() => run(() => clientApi.putClientManager(c.id, null, false), "Manager removed.")} />}
    </section>
  );
}
