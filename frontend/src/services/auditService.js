import { api } from "./apiClient";

const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v != null));
export const listAuditLogs = (params) => api.get("/audit-logs", { params: clean(params) }).then((r) => r.data);
