import axios from "axios";

// Single API client. Cookie-based auth (added in Stage 2) requires credentials.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  withCredentials: true,
  timeout: 15000,
});

// Normalises backend errors to { status, code, message }.
export function toApiError(err) {
  const data = err?.response?.data?.error;
  return {
    status: err?.response?.status ?? 0,
    code: data?.code ?? (err?.response ? "request_failed" : "network_error"),
    message: data?.message ?? (err?.response ? "Request failed." : "Cannot reach the server."),
  };
}

api.interceptors.response.use(
  (r) => r,
  (err) => Promise.reject(toApiError(err))
);
