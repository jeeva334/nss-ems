import { useEffect, useRef } from "react";

export default function ConfirmDialog({ title, message, confirmLabel, danger, busy, onConfirm, onCancel }) {
  const cancelRef = useRef(null);
  useEffect(() => {
    cancelRef.current?.focus();
    const onKey = (e) => e.key === "Escape" && onCancel();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onCancel]);
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-900/50 p-4">
      <div role="dialog" aria-modal="true" aria-labelledby="dlg-title" className="w-full max-w-sm rounded-2xl bg-white p-6 shadow-xl">
        <h2 id="dlg-title" className="text-lg font-semibold">{title}</h2>
        <p className="mt-2 text-sm text-slate-600">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button ref={cancelRef} onClick={onCancel} className="rounded-lg border border-slate-300 px-4 py-2 text-sm">Cancel</button>
          <button onClick={onConfirm} disabled={busy}
            className={`rounded-lg px-4 py-2 text-sm text-white disabled:opacity-60 ${danger ? "bg-red-600 hover:bg-red-700" : "bg-blue-600 hover:bg-blue-700"}`}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
