import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import * as authService from "../services/authService";
import { setCsrfToken, setUnauthorizedHandler } from "../services/apiClient";

const AuthContext = createContext(null);
export const useAuth = () => useContext(AuthContext);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sessionExpired, setSessionExpired] = useState(false);

  const apply = useCallback((session) => {
    setCsrfToken(session?.csrf_token ?? null);
    setUser(session?.user ?? null);
  }, []);

  useEffect(() => {
    authService.getMe().then(apply, () => apply(null)).finally(() => setLoading(false));
    setUnauthorizedHandler(() => { apply(null); setSessionExpired(true); });
  }, [apply]);

  const value = useMemo(() => ({
    user, loading, sessionExpired,
    login: async (identifier, password) => { apply(await authService.login(identifier, password)); setSessionExpired(false); },
    logout: async () => { try { await authService.logout(); } finally { apply(null); } },
  }), [user, loading, sessionExpired, apply]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
