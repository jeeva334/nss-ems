import { api } from "./apiClient";

const clean = (o) => Object.fromEntries(Object.entries(o).filter(([, v]) => v !== "" && v != null));

export const listUsers = (params) => api.get("/users", { params: clean(params) }).then((r) => r.data);
export const createUser = (body) => api.post("/users", body).then((r) => r.data);
export const getUser = (id) => api.get(`/users/${id}`).then((r) => r.data);
export const updateUser = (id, body) => api.patch(`/users/${id}`, body).then((r) => r.data);
export const setUserStatus = (id, status) => api.patch(`/users/${id}/status`, { status }).then((r) => r.data);
export const sendInvitation = (id) => api.post(`/users/${id}/invitations`).then((r) => r.data);
export const revokeInvitation = (id) => api.post(`/users/${id}/invitations/revoke`);
export const activateAccount = (token, password, confirm_password) =>
  api.post("/auth/activate", { token, password, confirm_password }).then((r) => r.data);
