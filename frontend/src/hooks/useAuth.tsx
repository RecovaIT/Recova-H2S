"use client";

import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import { ApiError } from "@/lib/api";
import { authService, type BootstrapPayload, type LoginPayload } from "@/services/auth";
import type { SessionResponse } from "@/types/recova";

interface AuthContextValue {
  session: SessionResponse | null;
  loading: boolean;
  needsBootstrap: boolean;
  error: string | null;
  refreshSession: () => Promise<void>;
  login: (payload: LoginPayload) => Promise<SessionResponse>;
  bootstrap: (payload: BootstrapPayload) => Promise<SessionResponse>;
  logout: () => Promise<void>;
  switchOrganization: (orgId: string) => Promise<void>;
  hasPermission: (perm: string) => boolean;
  hasTrack: (track: string) => boolean;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSession] = useState<SessionResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [needsBootstrap, setNeedsBootstrap] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadSession = useCallback(async () => {
    try {
      const statusRes = await authService.status();
      setNeedsBootstrap(Boolean(statusRes.needs_bootstrap));
      if (statusRes.needs_bootstrap) {
        setSession(null);
        setError(null);
        return;
      }
      try {
        const me = await authService.me();
        setSession(me);
        setError(null);
      } catch (err) {
        if (err instanceof ApiError && err.status === 401) {
          setSession(null);
          setError(null);
        } else {
          setError(err instanceof Error ? err.message : "Failed to verify session");
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Backend API unreachable");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const timer = setTimeout(() => {
      void loadSession();
    }, 0);
    return () => clearTimeout(timer);
  }, [loadSession]);

  const refreshSession = useCallback(async () => {
    setLoading(true);
    await loadSession();
  }, [loadSession]);

  const login = useCallback(async (payload: LoginPayload) => {
    const res = await authService.login(payload);
    setSession(res);
    setNeedsBootstrap(false);
    setError(null);
    return res;
  }, []);

  const bootstrap = useCallback(async (payload: BootstrapPayload) => {
    const res = await authService.bootstrap(payload);
    setSession(res);
    setNeedsBootstrap(false);
    setError(null);
    return res;
  }, []);

  const logout = useCallback(async () => {
    try {
      await authService.logout();
    } finally {
      setSession(null);
    }
  }, []);

  const switchOrganization = useCallback(async (orgId: string) => {
    const res = await authService.switchOrganization(orgId);
    setSession(res);
  }, []);

  const hasPermission = useCallback(
    (perm: string) => {
      if (!session) return false;
      return session.permissions.includes(perm);
    },
    [session]
  );

  const hasTrack = useCallback(
    (track: string) => {
      if (!session) return false;
      return session.tracks.includes(track);
    },
    [session]
  );

  return (
    <AuthContext.Provider
      value={{
        session,
        loading,
        needsBootstrap,
        error,
        refreshSession,
        login,
        bootstrap,
        logout,
        switchOrganization,
        hasPermission,
        hasTrack,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used inside AuthProvider");
  }
  return ctx;
}
