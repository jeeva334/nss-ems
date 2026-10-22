import { useCallback, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, ArrowLeft, Loader2 } from "lucide-react";
import { editUserSchema } from "../schemas/userSchemas";
import * as users from "../services/userService";
import { useAsync } from "../hooks/useAsync";
import { useAuth } from "../hooks/AuthContext";
import StatusBadge from "../components/StatusBadge";
import ConfirmDialog from "../components/ConfirmDialog";
import AssignmentSection from "../components/AssignmentPanels";
import { card, Row } from "../components/ui";


function EditForm({ user, onSaved, onCancel }) {
  const [err, setErr] = useState(null);
  const { register, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(editUserSchema),
    defaultValues: { full_name: user.full_name, mobile_number: user.mobile_number, email: user.email },
  });
  const submit = async (v) => {
    try { await users.updateUser(user.id, v); onSaved(); }
    catch (e) {
      if (e.code === "duplicate_email") setError("email", { message: "A user with this email already exists." });
      else setErr(e.message);
    }
  };
  const f = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm";
  return (
    <form onSubmit={handleSubmit(submit)} noValidate className="space-y-3">
      {err && <p role="alert" className="text-sm text-red-700">{err}</p>}
      {[["full_name", "Full name"], ["mobile_number", "Mobile number"], ["email", "Email address"]].map(([n, l]) => (
        <div key={n}><label htmlFor={`e_${n}`} className="text-sm font-medium">{l}</label>
          <input id={`e_${n}`} className={f} {...register(n)} />
          {errors[n] && <p className="text-sm text-red-600">{errors[n].message}</p>}</div>))}
      {user.status === "PENDING" && <p className="text-xs text-amber-700">Changing the email cancels the current invitation; send a new one afterwards.</p>}
      <div className="flex gap-2">
        <button disabled={isSubmitting} className="rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white disabled:opacity-60">Save changes</button>
        <button type="button" onClick={onCancel} className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm">Cancel</button>
      </div>
    </form>
  );
}

export default function UserDetailPage() {
  const { id } = useParams();
  const { user: me } = useAuth();
  const fetcher = useCallback(() => users.getUser(id), [id]);
  const { loading, data, error, retry } = useAsync(fetcher);
  const [notice, setNotice] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);

  const run = async (fn, okText) => {
    setBusy(true);
    try { const res = await fn(); const out = okText(res); setNotice(typeof out === "string" ? { ok: true, text: out } : out); setConfirm(null); setEditing(false); retry(); }
    catch (e) { setNotice({ ok: false, text: e.message }); setConfirm(null); }
    finally { setBusy(false); }
  };

  if (loading) return <p className="flex items-center gap-2 text-slate-600"><Loader2 className="animate-spin" size={16} /> Loading user…</p>;
  if (error) return (
    <div role="alert" className="text-red-700"><p className="flex items-center gap-2"><AlertTriangle size={16} /> {error.status === 404 ? "This user does not exist." : error.message}</p>
      {error.status !== 404 && <button onClick={retry} className="mt-3 rounded-lg bg-blue-600 px-3 py-1.5 text-sm text-white">Retry</button>}</div>);

  const { user, invitation: inv, assignments } = data;
  const canRevoke = inv && ["SENT", "SEND_FAILED"].includes(inv.state);
  const deliveryText = (r) => r.delivery.status === "sent"
    ? { ok: true, text: r.delivery.provider === "dev_outbox" ? "Invitation saved to the development outbox (not emailed)." : "Invitation accepted by the email provider." }
    : { ok: false, text: `Invitation created but email delivery failed (${r.delivery.error}). You can retry.` };
  const btn = "rounded-lg border border-slate-300 px-3 py-1.5 text-sm hover:bg-slate-50 disabled:opacity-50";

  return (
    <section className="max-w-4xl">
      <Link to="/users" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-600 hover:underline"><ArrowLeft size={14} /> Users</Link>
      <div className="flex flex-wrap items-center gap-3"><h1 className="text-2xl font-semibold">{user.full_name}</h1><StatusBadge value={user.status} /></div>
      {notice && <p role={notice.ok ? "status" : "alert"} className={`mt-3 rounded-lg p-3 text-sm ${notice.ok ? "bg-green-50 text-green-800" : "bg-red-50 text-red-700"}`}>{notice.text}</p>}

      <div className="mt-5 grid gap-5 md:grid-cols-2">
        <div className={card}>
          <h2 className="font-semibold">Profile</h2>
          {editing ? <div className="mt-3"><EditForm user={user} onCancel={() => setEditing(false)} onSaved={() => { setNotice({ ok: true, text: "Profile updated." }); setEditing(false); retry(); }} /></div> : (
            <dl className="mt-2 divide-y">
              <Row label="Employee ID">{user.employee_id}</Row><Row label="Email">{user.email}</Row>
              <Row label="Mobile">{user.mobile_number}</Row><Row label="Role">{user.role.charAt(0) + user.role.slice(1).toLowerCase()}</Row>
              <Row label="Created">{new Date(user.created_at).toLocaleDateString()}</Row>
              <Row label="Last sign-in">{user.last_login_at ? new Date(user.last_login_at).toLocaleString() : "Never"}</Row>
            </dl>)}
          {!editing && <button className={`${btn} mt-3`} onClick={() => setEditing(true)}>Edit profile</button>}
        </div>

        <div className={card}>
          <h2 className="font-semibold">Account &amp; invitation</h2>
          <dl className="mt-2 divide-y">
            <Row label="Account status"><StatusBadge value={user.status} /></Row>
            {inv && <Row label="Latest invitation"><StatusBadge value={inv.state} /></Row>}
            {inv && <Row label="Expires">{new Date(inv.expires_at).toLocaleString()}</Row>}
            {inv?.send_error && <Row label="Delivery error">{inv.send_error}</Row>}
          </dl>
          <div className="mt-3 flex flex-wrap gap-2">
            {user.status === "PENDING" && <button className={btn} disabled={busy} onClick={() => run(() => users.sendInvitation(user.id), deliveryText)}>{inv ? "Resend invitation" : "Send invitation"}</button>}
            {canRevoke && <button className={btn} disabled={busy} onClick={() => setConfirm("revoke")}>Revoke invitation</button>}
            {user.status !== "INACTIVE" && user.id !== me.id && <button className={`${btn} text-red-700`} disabled={busy} onClick={() => setConfirm("deactivate")}>Deactivate account</button>}
            {user.status === "INACTIVE" && <button className={btn} disabled={busy} onClick={() => run(() => users.setUserStatus(user.id, "ACTIVE"),
              (u) => u.status === "PENDING" ? "Account moved to Pending. Send a new invitation to let the user set a password." : "Account reactivated.")}>Reactivate account</button>}
          </div>
        </div>
      </div>

      <div className="mt-5"><AssignmentSection user={user} a={assignments} onChanged={(n) => { setNotice(n); retry(); }} /></div>

      {confirm === "revoke" && <ConfirmDialog title="Revoke invitation?" message="The activation link will stop working immediately." confirmLabel="Revoke" danger busy={busy} onCancel={() => setConfirm(null)}
        onConfirm={() => run(() => users.revokeInvitation(user.id), () => "Invitation revoked.")} />}
      {confirm === "deactivate" && <ConfirmDialog title="Deactivate this account?" message="The user is signed out immediately and cannot sign in until reactivated." confirmLabel="Deactivate" danger busy={busy} onCancel={() => setConfirm(null)}
        onConfirm={() => run(() => users.setUserStatus(user.id, "INACTIVE"), () => "Account deactivated.")} />}
    </section>
  );
}
