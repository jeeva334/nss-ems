import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "react-router-dom";
import { AlertTriangle, Loader2 } from "lucide-react";
import { createClientSchema } from "../schemas/clientSchemas";
import { createClient } from "../services/clientService";

const input = "mt-1 w-full rounded-lg border border-slate-300 px-3 py-2";
const FIELDS = [["client_code", "Client code"], ["client_name", "Client name"], ["address", "Address"],
  ["contact_name", "Contact name"], ["contact_email", "Contact email"], ["contact_phone", "Contact phone"]];

export default function CreateClientPage() {
  const navigate = useNavigate();
  const [formError, setFormError] = useState(null);
  const { register, handleSubmit, setError, formState: { errors, isSubmitting, isDirty, isSubmitSuccessful } } = useForm({
    resolver: zodResolver(createClientSchema),
    defaultValues: { client_code: "", client_name: "", address: "", contact_name: "", contact_email: "", contact_phone: "" },
  });
  useEffect(() => {
    if (!isDirty || isSubmitSuccessful) return;
    const h = (e) => { e.preventDefault(); e.returnValue = ""; };
    window.addEventListener("beforeunload", h);
    return () => window.removeEventListener("beforeunload", h);
  }, [isDirty, isSubmitSuccessful]);

  const onSubmit = async (values) => {
    setFormError(null);
    try { navigate(`/clients/${(await createClient(values)).id}`); }
    catch (e) {
      if (e.code === "duplicate_client_code") setError("client_code", { message: "A client with this code already exists." });
      else if (e.fields?.length) e.fields.forEach((f) => setError(f.field, { message: f.message }));
      else setFormError(e.message);
    }
  };
  return (
    <section className="max-w-xl">
      <h1 className="text-2xl font-semibold">Create Client</h1>
      <p className="mt-1 text-slate-600">Assign a Manager after the client is created.</p>
      <form onSubmit={handleSubmit(onSubmit)} noValidate className="mt-6 rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {formError && <p role="alert" className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700"><AlertTriangle size={16} /> {formError}</p>}
        {FIELDS.map(([n, l], i) => (
          <div key={n} className={i ? "mt-4" : ""}>
            <label htmlFor={n} className="block text-sm font-medium">{l}</label>
            <input id={n} className={input} {...register(n)} aria-invalid={!!errors[n]} />
            {errors[n] && <p className="mt-1 text-sm text-red-600">{errors[n].message}</p>}
          </div>))}
        <div className="mt-6 flex items-center gap-3">
          <button type="submit" disabled={isSubmitting} className="flex items-center gap-2 rounded-lg bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:opacity-60">
            {isSubmitting && <Loader2 className="animate-spin" size={16} />} CREATE CLIENT</button>
          <Link to="/clients" className="text-sm text-slate-600 hover:underline">Cancel</Link>
        </div>
      </form>
    </section>
  );
}
