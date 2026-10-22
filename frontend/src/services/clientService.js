import { api } from "./apiClient";

const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v != null));

export const listClients = (params) => api.get("/clients", { params: clean(params) }).then((r) => r.data);
export const createClient = (body) => api.post("/clients", body).then((r) => r.data);
export const getClient = (id) => api.get(`/clients/${id}`).then((r) => r.data);
export const updateClient = (id, body) => api.patch(`/clients/${id}`, body).then((r) => r.data);
export const setClientStatus = (id, status) => api.patch(`/clients/${id}/status`, { status }).then((r) => r.data);
export const putClientManager = (id, manager_id, reassign = false) =>
  api.put(`/clients/${id}/manager`, { manager_id, reassign }).then((r) => r.data);
