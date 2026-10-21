import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { AlertTriangle, Loader2 } from "lucide-react";
import { loginSchema } from "../schemas/authSchemas";
import { useAuth } from "../hooks/AuthContext";

export default function LoginPage() {
  const { user, login, sessionExpired } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [serverError, setServerError] = useState(null);
  const { register, handleSubmit, formState: { errors, isSubmitting } } = useForm({
    resolver: zodResolver(loginSchema),
  });

  if (user) return <Navigate to="/" replace />;

  const onSubmit = async ({ identifier, password }) => {
    setServerError(null);
    try {
      await login(identifier, password);
      navigate(location.state?.from || "/", { replace: true });
    } catch (e) {
      setServerError(e.status === 429 ? e.message : e.status === 401 ? "Employee ID, email or password is incorrect." : e.message);
    }
  };

  const field = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 focus:border-blue-600";
  return (
    <div className="min-h-screen grid place-items-center bg-slate-100 p-4">
      <form onSubmit={handleSubmit(onSubmit)} noValidate
        className="w-full max-w-sm rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <h1 className="text-xl font-semibold">Sign in</h1>
        <p className="mt-1 text-sm text-slate-600">Use your Employee ID or email.</p>
        {sessionExpired && <p role="status" className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">Your session expired. Sign in again to continue.</p>}
        {serverError && (
          <p role="alert" className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700">
            <AlertTriangle size={16} aria-hidden /> {serverError}
          </p>
        )}
        <label className="mt-4 block text-sm font-medium" htmlFor="identifier">Employee ID or email</label>
        <input id="identifier" autoComplete="username" className={field} {...register("identifier")}
          aria-invalid={!!errors.identifier} />
        {errors.identifier && <p className="mt-1 text-sm text-red-600">{errors.identifier.message}</p>}
        <label className="mt-4 block text-sm font-medium" htmlFor="password">Password</label>
        <input id="password" type="password" autoComplete="current-password" className={field}
          {...register("password")} aria-invalid={!!errors.password} />
        {errors.password && <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>}
        <button type="submit" disabled={isSubmitting}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 py-2 font-medium text-white hover:bg-blue-700 disabled:opacity-60">
          {isSubmitting && <Loader2 className="animate-spin" size={16} />} Sign in
        </button>
      </form>
    </div>
  );
}
