import { api } from "./apiClient";

export const login = (identifier, password) =>
  api.post("/auth/login", { identifier, password }).then((r) => r.data);
export const logout = () => api.post("/auth/logout");
export const getMe = () => api.get("/auth/me").then((r) => r.data);
