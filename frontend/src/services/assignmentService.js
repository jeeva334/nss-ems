import { api } from "./apiClient";

export const mapSupervisorManager = (id, manager_id, clear_client = false) =>
  api.put(`/users/${id}/manager`, { manager_id, clear_client }).then((r) => r.data);
// The Manager is never sent: the backend uses the existing mapping and validates the client against it.
export const assignSupervisorClient = (id, client_id) => api.put(`/users/${id}/client`, { client_id }).then((r) => r.data);
export const getAssignments = (id) => api.get(`/users/${id}/assignments`).then((r) => r.data);
