"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";

const TOKEN_KEY = "vkorni_admin_token";

export function useAdmin() {
  const [token, setToken] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  // Rehydrate token from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    if (stored) setToken(stored);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    setBusy(true);
    setError("");
    try {
      const data = await api.adminLogin(username, password);
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chyba přihlášení");
    } finally {
      setBusy(false);
    }
  }, []);

  const setup = useCallback(async (username: string, password: string) => {
    setBusy(true);
    setError("");
    try {
      await api.adminSetup(username, password);
      // Auto-login after setup
      const data = await api.adminLogin(username, password);
      localStorage.setItem(TOKEN_KEY, data.access_token);
      setToken(data.access_token);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Chyba nastavení");
    } finally {
      setBusy(false);
    }
  }, []);

  const changePassword = useCallback(
    async (currentPassword: string, newPassword: string) => {
      if (!token) return { ok: false, error: "Not authenticated" };
      setBusy(true);
      setError("");
      try {
        await api.adminChangePassword(token, currentPassword, newPassword);
        return { ok: true };
      } catch (err) {
        const msg = err instanceof Error ? err.message : "Chyba změny hesla";
        setError(msg);
        return { ok: false, error: msg };
      } finally {
        setBusy(false);
      }
    },
    [token]
  );

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setError("");
  }, []);

  return {
    token,
    isLoggedIn: !!token,
    busy,
    error,
    login,
    setup,
    changePassword,
    logout,
  };
}
