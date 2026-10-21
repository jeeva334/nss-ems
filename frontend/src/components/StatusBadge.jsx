const STYLES = {
  ACTIVE: "bg-green-100 text-green-800", PENDING: "bg-amber-100 text-amber-800",
  INACTIVE: "bg-slate-200 text-slate-700", SENT: "bg-blue-100 text-blue-800",
  SEND_FAILED: "bg-red-100 text-red-800", EXPIRED: "bg-slate-200 text-slate-700",
  REVOKED: "bg-slate-200 text-slate-700", ACCEPTED: "bg-green-100 text-green-800",
};
const LABEL = { SEND_FAILED: "Email failed" };

export default function StatusBadge({ value }) {
  const text = LABEL[value] || value.charAt(0) + value.slice(1).toLowerCase();
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[value] || STYLES.INACTIVE}`}>{text}</span>;
}
