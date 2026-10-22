import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { useAsync } from "../hooks/useAsync";
import * as clientApi from "../services/clientService";
import * as assignApi from "../services/assignmentService";
import * as userApi from "../services/userService";
import ConfirmDialog from "./ConfirmDialog";
import { btn, card, conflictMessage, primary, Row, select } from "./ui";

function useAction(onChanged) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const run = async (fn, okText, handled) => {
    setBusy(true); setError(null);
    try { await fn(); onChanged({ ok: true, text: okText }); }
    catch (e) { if (!(handled && handled(e))) setError(conflictMessage(e)); }
    finally { setBusy(false); }
  };
  return { busy, error, run };
}
const Err = ({ text }) => (text ? <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{text}</p> : null);
const items = (r) => r.data?.items ?? [];

function ManagerPanel({ user, a, onChanged }) {
  const { busy, error, run } = useAction(onChanged);
  const free = useAsync(useCallback(() => clientApi.listClients({ unassigned: true, status: "ACTIVE", page_size: 100 }), []));
  const unmapped = useAsync(useCallback(() => userApi.listUsers({ role: "SUPERVISOR", mapped: false, page_size: 100 }), []));
  const [clientId, setClientId] = useState("");
  const [supId, setSupId] = useState("");
  const [confirm, setConfirm] = useState(null);
  const mappable = items(unmapped).filter((s) => s.status !== "INACTIVE");
  const inactive = user.status !== "ACTIVE";

  return (
    <div className={card}>
      <h2 className="font-semibold">Assigned clients</h2>
      {a.clients?.length ? (
        <ul className="mt-2 divide-y text-sm">{a.clients.map((c) => (
          <li key={c.id} className="flex items-center justify-between gap-2 py-2">
            <span>{c.client_name} <span className="text-slate-500">({c.client_code})</span></span>
            <span className="flex gap-2">
              <Link className={btn} to={`/clients/${c.id}`}>Reassign…</Link>
              <button className={btn} disabled={busy} onClick={() => setConfirm({ kind: "removeClient", c })} aria-label={`Remove ${c.client_name}`}>Remove</button>
            </span>
          </li>))}</ul>
      ) : <p className="mt-2 text-sm text-slate-600">No clients assigned yet.</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label htmlFor="client-to-assign" className="sr-only">Client to assign</label>
        <select id="client-to-assign" className={select} value={clientId} onChange={(e) => setClientId(e.target.value)} disabled={inactive}>
          <option value="">Unassigned clients…</option>
          {items(free).map((c) => <option key={c.id} value={c.id}>{c.client_name} ({c.client_code})</option>)}
        </select>
        <button className={primary} disabled={!clientId || busy || inactive}
          onClick={() => run(() => clientApi.putClientManager(Number(clientId), user.id, false), "Client assigned.")}>Assign client</button>
      </div>
      <p className="mt-1 text-xs text-slate-500">Clients that already have a Manager are moved from their client page (explicit reassignment).</p>

      <h2 className="mt-6 font-semibold">Supervisors under this Manager</h2>
      {a.supervisors?.length ? (
        <ul className="mt-2 divide-y text-sm">{a.supervisors.map((s) => (
          <li key={s.id} className="flex items-center justify-between gap-2 py-2">
            <span><Link className="text-blue-700 hover:underline" to={`/users/${s.id}`}>{s.full_name}</Link> <span className="text-slate-500">{s.employee_id}</span></span>
            <button className={btn} disabled={busy} onClick={() => setConfirm({ kind: "unmap", s })} aria-label={`Unmap ${s.full_name}`}>Unmap</button>
          </li>))}</ul>
      ) : <p className="mt-2 text-sm text-slate-600">No Supervisors mapped yet.</p>}
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label htmlFor="sup-to-map" className="sr-only">Supervisor to map</label>
        <select id="sup-to-map" className={select} value={supId} onChange={(e) => setSupId(e.target.value)} disabled={inactive}>
          <option value="">Unmapped Supervisors…</option>
          {mappable.map((s) => <option key={s.id} value={s.id}>{s.full_name} ({s.employee_id})</option>)}
        </select>
        <button className={primary} disabled={!supId || busy || inactive}
          onClick={() => run(() => assignApi.mapSupervisorManager(Number(supId), user.id, false), "Supervisor mapped.")}>Map supervisor</button>
      </div>
      <Err text={error} />

      {confirm?.kind === "removeClient" && <ConfirmDialog title="Remove client from this Manager?" confirmLabel="Remove" danger busy={busy}
        message={`${confirm.c.client_name} will have no Manager. This is blocked while Supervisors are assigned to it.`}
        onCancel={() => setConfirm(null)} onConfirm={() => { const c = confirm.c; setConfirm(null); run(() => clientApi.putClientManager(c.id, null, false), "Client removed from Manager."); }} />}
      {confirm?.kind === "unmap" && <ConfirmDialog title="Unmap this Supervisor?" confirmLabel="Unmap" danger busy={busy}
        message={`${confirm.s.full_name} will have no Manager and any client assignment will be cleared.`}
        onCancel={() => setConfirm(null)} onConfirm={() => { const s = confirm.s; setConfirm(null); run(() => assignApi.mapSupervisorManager(s.id, null, false), "Supervisor unmapped."); }} />}
    </div>
  );
}

function SupervisorPanel({ user, a, onChanged }) {
  const { busy, error, run } = useAction(onChanged);
  const mgrId = a.manager?.id;
  const managers = useAsync(useCallback(() => userApi.listUsers({ role: "MANAGER", status: "ACTIVE", page_size: 100 }), []));
  // Only clients currently assigned to the Supervisor's mapped Manager are offered.
  const eligible = useAsync(useCallback(() => (mgrId
    ? clientApi.listClients({ manager_id: mgrId, status: "ACTIVE", page_size: 100 }) : Promise.resolve({ items: [] })), [mgrId]));
  const [newMgr, setNewMgr] = useState("");
  const [clientId, setClientId] = useState("");
  const [confirm, setConfirm] = useState(null);
  const inactive = user.status === "INACTIVE";
  const otherManagers = items(managers).filter((m) => m.id !== mgrId);

  const changeManager = () => run(() => assignApi.mapSupervisorManager(user.id, Number(newMgr), false), "Manager mapping updated.",
    (e) => { if (e.code === "has_client_assignment") { setConfirm({ kind: "clear", managerId: Number(newMgr), client: e.details?.client }); return true; } return false; });

  return (
    <div className={card}>
      <h2 className="font-semibold">Manager and client</h2>
      {inactive && <p className="mt-2 text-sm text-amber-700">This account is inactive. Reactivate it before changing assignments.</p>}
      <dl className="mt-2 divide-y">
        <Row label="Manager (read-only)">{a.manager ? <Link className="text-blue-700 hover:underline" to={`/users/${a.manager.id}`}>{`${a.manager.full_name} (${a.manager.employee_id})`}</Link> : "Not mapped"}</Row>
        <Row label="Client">{a.client ? `${a.client.client_name} (${a.client.client_code})` : "Not assigned"}</Row>
      </dl>

      <h3 className="mt-5 text-sm font-semibold">Client assignment</h3>
      {!a.manager ? <p className="mt-1 text-sm text-slate-600">Map a Manager first; clients come from that Manager.</p> : (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <label htmlFor="sup-client" className="sr-only">Client</label>
          <select id="sup-client" className={select} value={clientId} onChange={(e) => setClientId(e.target.value)} disabled={inactive}>
            <option value="">Clients of this Manager…</option>
            {items(eligible).map((c) => <option key={c.id} value={c.id}>{c.client_name} ({c.client_code})</option>)}
          </select>
          <button className={primary} disabled={!clientId || busy || inactive}
            onClick={() => run(() => assignApi.assignSupervisorClient(user.id, Number(clientId)), a.client ? "Client changed." : "Client assigned.")}>
            {a.client ? "Change client" : "Assign client"}</button>
          {a.client && <button className={btn} disabled={busy || inactive} onClick={() => run(() => assignApi.assignSupervisorClient(user.id, null), "Client assignment cleared.")}>Clear client</button>}
        </div>)}

      <h3 className="mt-5 text-sm font-semibold">Change Manager mapping</h3>
      <p className="text-xs text-slate-500">A separate, explicit action. Changing the Manager clears the current client assignment.</p>
      <div className="mt-2 flex flex-wrap items-center gap-2">
        <label htmlFor="new-manager" className="sr-only">Select new Manager</label>
        <select id="new-manager" className={select} value={newMgr} onChange={(e) => setNewMgr(e.target.value)} disabled={inactive}>
          <option value="">{a.manager ? "Select new Manager…" : "Select Manager…"}</option>
          {otherManagers.map((m) => <option key={m.id} value={m.id}>{m.full_name} ({m.employee_id})</option>)}
        </select>
        <button className={primary} disabled={!newMgr || busy || inactive} onClick={changeManager}>{a.manager ? "Change Manager" : "Map to Manager"}</button>
        {a.manager && <button className={btn} disabled={busy} onClick={() => setConfirm({ kind: "unmap" })}>Remove mapping</button>}
      </div>
      <Err text={error} />

      {confirm?.kind === "clear" && <ConfirmDialog title="Change Manager and clear client?" confirmLabel="Change Manager" danger busy={busy}
        message={`${user.full_name} is assigned to ${confirm.client ? confirm.client.client_name : "a client"} of the current Manager. That client assignment will be cleared.`}
        onCancel={() => setConfirm(null)} onConfirm={() => { const m = confirm.managerId; setConfirm(null); run(() => assignApi.mapSupervisorManager(user.id, m, true), "Manager changed; client assignment cleared."); }} />}
      {confirm?.kind === "unmap" && <ConfirmDialog title="Remove Manager mapping?" confirmLabel="Remove mapping" danger busy={busy}
        message="The Supervisor will have no Manager and no client." onCancel={() => setConfirm(null)}
        onConfirm={() => { setConfirm(null); run(() => assignApi.mapSupervisorManager(user.id, null, false), "Manager mapping removed."); }} />}
    </div>
  );
}

const EVENT = {
  client_manager_assigned: "Client assigned to Manager", client_manager_reassigned: "Client reassigned to Manager",
  client_manager_removed: "Client removed from Manager", supervisor_mapped: "Supervisor mapped to Manager",
  supervisor_remapped: "Supervisor moved to Manager", supervisor_unmapped: "Supervisor unmapped",
  supervisor_unmapped_on_deactivation: "Supervisor unmapped (account deactivated)",
  supervisor_client_assigned: "Client assigned to Supervisor", supervisor_client_changed: "Supervisor's client changed",
  supervisor_client_cleared: "Supervisor's client cleared",
};

function HistoryPanel({ userId }) {
  const { loading, data } = useAsync(useCallback(() => assignApi.getAssignments(userId), [userId]));
  const rows = data?.history ?? [];
  return (
    <div className={card}>
      <h2 className="font-semibold">Assignment history</h2>
      {loading ? <p className="mt-2 text-sm text-slate-500">Loading…</p> : rows.length === 0 ? <p className="mt-2 text-sm text-slate-600">No assignment changes yet.</p> : (
        <ul className="mt-2 divide-y text-sm">{rows.map((h) => (
          <li key={h.id} className="py-2">
            <span className="font-medium">{EVENT[h.event_type] || h.event_type}</span>
            <span className="text-slate-600"> — {[h.supervisor, h.manager, h.client_code].filter(Boolean).join(" · ")}</span>
            <span className="block text-xs text-slate-500">{new Date(h.created_at).toLocaleString()}{h.actor ? ` by ${h.actor}` : ""}</span>
          </li>))}</ul>)}
    </div>
  );
}

export default function AssignmentSection({ user, a, onChanged }) {
  if (user.role === "ADMIN") return <div className={card}><h2 className="font-semibold">Administrative profile</h2><p className="mt-2 text-sm text-slate-600">Admins have company-wide access and no client assignments.</p></div>;
  return (
    <div className="space-y-5">
      {user.role === "MANAGER" ? <ManagerPanel user={user} a={a} onChanged={onChanged} /> : <SupervisorPanel user={user} a={a} onChanged={onChanged} />}
      <HistoryPanel userId={user.id} />
    </div>
  );
}
