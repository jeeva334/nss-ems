import axios from "axios";

// Single API client. Auth is a HttpOnly session cookie; the CSRF token is kept in memory only.
export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "/api/v1",
  withCredentials: true,
  timeout: 15000,
});

let csrfToken = null;
export const setCsrfToken = (t) => { csrfToken = t; };

api.interceptors.request.use((config) => {
  if (csrfToken && !["get", "head", "options"].includes((config.method || "get").toLowerCase())) {
    config.headers["X-CSRF-Token"] = csrfToken;
  }
  return config;
});

// Normalises backend errors to { status, code, message, fields }.
export function toApiError(err) {
  const data = err?.response?.data?.error;
  return {
    status: err?.response?.status ?? 0,
    code: data?.code ?? (err?.response ? "request_failed" : "network_error"),
    message: data?.message ?? (err?.response ? "Request failed." : "Cannot reach the server."),
    fields: data?.details?.fields ?? [],
  };
}

// Handlers registered by the auth context to react to expired sessions.
let onUnauthorized = null;
export const setUnauthorizedHandler = (fn) => { onUnauthorized = fn; };

api.interceptors.response.use(
  (r) => r,
  (err) => {
    const apiErr = toApiError(err);
    const isAuthCall = err?.config?.url?.startsWith("/auth/");
    if (apiErr.status === 401 && !isAuthCall && onUnauthorized) onUnauthorized();
    return Promise.reject(apiErr);
  }
);
