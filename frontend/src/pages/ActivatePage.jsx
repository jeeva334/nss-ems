import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Loader2 } from "lucide-react";
import { activateSchema } from "../schemas/userSchemas";
import { activateAccount } from "../services/userService";

export default function ActivatePage() {
  const [token, setToken] = useState(null);
  const [done, setDone] = useState(false);
  const [serverError, setServerError] = useState(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({ resolver: zodResolver(activateSchema) });

  useEffect(() => {  // token lives in the URL fragment (never sent to servers); remove it from the address bar
    const t = new URLSearchParams(window.location.hash.slice(1)).get("token");
    setToken(t || "");
    if (t) window.history.replaceState(null, "", window.location.pathname);
  }, []);

  const onSubmit = async (v) => {
    setServerError(null);
    try { await activateAccount(token, v.password, v.confirm_password); setDone(true); }
    catch (e) { setServerError(e.message); }
  };

  const f = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";
  return (
    <div className="grid min-h-screen place-items-center bg-slate-100 p-4">
      <div className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {token === null ? null : done ? (
          <div>
            <h1 className="flex items-center gap-2 text-xl font-semibold"><CheckCircle2 className="text-green-600" /> Account activated</h1>
            <p className="mt-2 text-sm text-slate-600">Your password is set. You can sign in now.</p>
            <Link to="/login" className="mt-5 inline-block rounded-lg bg-blue-600 px-4 py-2 text-sm text-white">Go to sign in</Link>
          </div>
        ) : !token ? (
          <div><h1 className="text-xl font-semibold">Invitation link incomplete</h1>
            <p className="mt-2 text-sm text-slate-600">Open the link from your invitation email again, or ask an administrator to send a new one.</p></div>
        ) : (
          <form onSubmit={handleSubmit(onSubmit)} noValidate>
            <h1 className="text-xl font-semibold">Set your password</h1>
            <p className="mt-1 text-sm text-slate-600">Use at least 12 characters with letters and digits.</p>
            {serverError && <p role="alert" className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700"><AlertTriangle size={16} /> {serverError}</p>}
            <label htmlFor="password" className="mt-4 block text-sm font-medium">New password</label>
            <input id="password" type="password" autoComplete="new-password" className={f} {...register("password")} />
            {errors.password && <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>}
            <label htmlFor="confirm_password" className="mt-4 block text-sm font-medium">Confirm password</label>
            <input id="confirm_password" type="password" autoComplete="new-password" className={f} {...register("confirm_password")} />
            {errors.confirm_password && <p className="mt-1 text-sm text-red-600">{errors.confirm_password.message}</p>}
            <button disabled={isSubmitting} className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-60">
              {isSubmitting && <Loader2 className="animate-spin" size={16} />} Activate account
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
