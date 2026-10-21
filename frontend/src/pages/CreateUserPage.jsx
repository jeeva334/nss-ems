import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { createUserSchema } from "../schemas/userSchemas";
import { createUser } from "../services/userService";

const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";

export default function CreateUserPage() {
  const [result, setResult] = useState(null);
  const [formError, setFormError] = useState(null);
  const { register, handleSubmit, reset, setError, formState: { errors, isSubmitting, isDirty } } = useForm({
    resolver: zodResolver(createUserSchema), defaultValues: { full_name: "", mobile_number: "", email: "", role: "" },
  });

  useEffect(() => {  // warn before losing unsaved input
    if (!isDirty || result) return;
    const h = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [isDirty, result]);

  const onSubmit = async (values) => {
    setFormError(null);
    try {
      setResult(await createUser(values));
    } catch (e) {
      if (e.code === "duplicate_email") setError("email", { message: "A user with this email already exists." });
      else if (e.fields?.length) e.fields.forEach((f) => setError(f.field, { message: f.message }));
      else setFormError(e.message);
    }
  };

  if (result) {
    const { user, delivery } = result;
    return (
      <section className="max-w-xl">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <h1 className="flex items-center gap-2 text-xl font-semibold"><CheckCircle2 className="text-green-600" /> Account created</h1>
          <p className="mt-3 text-slate-600">Employee ID: <strong className="text-slate-900">{user.employee_id}</strong> · {user.full_name}</p>
          {delivery.status === "sent" && delivery.provider !== "dev_outbox" && (
            <p className="mt-3 text-sm text-green-700">Invitation accepted by the email provider for {user.email}. It expires in 24 hours.</p>)}
          {delivery.status === "sent" && delivery.provider === "dev_outbox" && (
            <p className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Development mode: the invitation was saved to the local outbox, not emailed.</p>)}
          {delivery.status === "failed" && (
            <p role="alert" className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">
              The account exists but the invitation email could not be sent ({delivery.error}). Open the user and choose “Resend invitation”.</p>)}
          <div className="mt-6 flex gap-3">
            <Link to={`/users/${user.id}`} className="rounded-lg bg-blue-600 px-4 py-2 text-sm text-white">View user</Link>
            <button onClick={() => { setResult(null); reset(); }} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Create another</button>
          </div>
        </div>
      </section>
    );
  }

  const Err = ({ name }) => errors[name] ? <p className="mt-1 text-sm text-red-600">{errors[name].message}</p> : null;
  return (
    <section className="max-w-xl">
      <h1 className="text-2xl font-semibold">Create User</h1>
      <p className="mt-1 text-slate-600">The Employee ID is generated automatically. The user sets their own password from an emailed link.</p>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {formError && <p role="alert" className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700"><AlertTriangle size={16} /> {formError}</p>}
        <label htmlFor="full_name" className="block text-sm font-medium">Full name</label>
        <input id="full_name" className={input} {...register("full_name")} aria-invalid={!!errors.full_name} /><Err name="full_name" />
        <label htmlFor="mobile_number" className="mt-4 block text-sm font-medium">Mobile number</label>
        <input id="mobile_number" inputMode="tel" className={input} {...register("mobile_number")} aria-invalid={!!errors.mobile_number} /><Err name="mobile_number" />
        <label htmlFor="email" className="mt-4 block text-sm font-medium">Email address</label>
        <input id="email" type="email" className={input} {...register("email")} aria-invalid={!!errors.email} /><Err name="email" />
        <label htmlFor="role" className="mt-4 block text-sm font-medium">Role</label>
        <select id="role" className={input} {...register("role")} aria-invalid={!!errors.role}>
          <option value="">Select a role</option><option value="ADMIN">Admin</option>
          <option value="MANAGER">Manager</option><option value="SUPERVISOR">Supervisor</option>
        </select><Err name="role" />
        <div className="mt-6 flex items-center gap-3">
          <button type="submit" disabled={isSubmitting}
            className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
            {isSubmitting && <Loader2 className="animate-spin" size={16} />} CREATE USER &amp; SEND INVITATION
          </button>
          <Link to="/users" className="text-sm text-slate-600 hover:underline">Cancel</Link>
        </div>
      </form>
    </section>
  );
}
