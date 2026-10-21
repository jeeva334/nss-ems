import { api } from "./apiClient";

export const getReadiness = () => api.get("/health/ready").then((r) => r.data);
