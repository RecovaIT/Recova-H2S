import { api, clearCsrfToken, setCsrfToken } from "@/lib/api";
import type { SessionResponse } from "@/types/recova";

export interface BootstrapPayload {
  organization_name: string;
  organization_slug: string;
  org_type: "clinic" | "rehab_center" | "public_health" | "employer" | "hospital";
  primary_programme?: string;
  enabled_tracks: string[];
  admin_email: string;
  admin_full_name: string;
  admin_password: string;
  admin_license_number?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
  organization_id?: string;
}

export const authService = {
  async status(): Promise<{ needs_bootstrap: boolean }> {
    return api.get("/auth/status");
  },

  async bootstrap(payload: BootstrapPayload): Promise<SessionResponse> {
    const res = await api.post<SessionResponse>("/auth/bootstrap", payload);
    setCsrfToken(res.csrf_token);
    return res;
  },

  async registerOrganization(payload: BootstrapPayload): Promise<SessionResponse> {
    const res = await api.post<SessionResponse>("/auth/register-organization", payload);
    setCsrfToken(res.csrf_token);
    return res;
  },

  async login(payload: LoginPayload): Promise<SessionResponse> {
    const res = await api.post<SessionResponse>("/auth/login", payload);
    setCsrfToken(res.csrf_token);
    return res;
  },

  async logout(): Promise<void> {
    await api.post("/auth/logout");
    clearCsrfToken();
  },

  async me(): Promise<SessionResponse> {
    const res = await api.get<SessionResponse>("/auth/me");
    setCsrfToken(res.csrf_token);
    return res;
  },

  async refreshCsrf(): Promise<string> {
    const res = await api.post<{ csrf_token: string }>("/auth/csrf");
    setCsrfToken(res.csrf_token);
    return res.csrf_token;
  },

  async switchOrganization(organization_id: string): Promise<SessionResponse> {
    const res = await api.post<SessionResponse>("/auth/switch-organization", {
      organization_id,
    });
    setCsrfToken(res.csrf_token);
    return res;
  },

  async requestPasswordReset(email: string): Promise<{ message: string; reset_token?: string }> {
    return api.post("/auth/password-reset/request", { email });
  },

  async confirmPasswordReset(token: string, new_password: string): Promise<{ message: string }> {
    return api.post("/auth/password-reset/confirm", { token, new_password });
  },

  async changePassword(current_password: string, new_password: string): Promise<{ message: string }> {
    return api.post("/auth/change-password", { current_password, new_password });
  },
};
