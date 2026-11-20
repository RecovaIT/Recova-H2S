import { watchIncomingPayload } from "@/lib/i18n-engine";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  details?: Record<string, unknown>;
  requestId?: string;

  constructor(
    message: string,
    status: number,
    code = "api_error",
    details?: Record<string, unknown>,
    requestId?: string
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }
}

let inMemoryCsrfToken: string | null = null;

export function setCsrfToken(token: string | null | undefined): void {
  if (token) {
    inMemoryCsrfToken = token;
  }
}

export function clearCsrfToken(): void {
  inMemoryCsrfToken = null;
}

export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const parts = document.cookie.split(";").map((p) => p.trim());
  for (const part of parts) {
    if (part.startsWith(`${name}=`)) {
      return decodeURIComponent(part.slice(name.length + 1));
    }
  }
  return null;
}

export function getCsrfToken(): string | null {
  return readCookie("recova_csrf") || inMemoryCsrfToken;
}

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

export interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  query?: Record<string, string | number | boolean | null | undefined>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  const base = `${API_BASE_URL.replace(/\/+$/, "")}${cleanPath}`;
  if (!query) return base;
  const params = new URLSearchParams();
  for (const [key, val] of Object.entries(query)) {
    if (val !== undefined && val !== null && val !== "") {
      params.set(key, String(val));
    }
  }
  const qs = params.toString();
  return qs ? `${base}?${qs}` : base;
}

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {}
): Promise<T> {
  const method = (options.method || "GET").toUpperCase();
  const headers = new Headers(options.headers);
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }

  if (MUTATING_METHODS.has(method)) {
    const csrf = getCsrfToken();
    if (csrf) {
      headers.set("X-CSRF-Token", csrf);
    }
  }

  const response = await fetch(buildUrl(path, options.query), {
    ...options,
    method,
    headers,
    credentials: "include",
    body:
      options.body === undefined
        ? undefined
        : options.body instanceof FormData
        ? options.body
        : JSON.stringify(options.body),
  });

  const contentType = response.headers.get("content-type") || "";
  const isJson = contentType.includes("application/json");
  const payload = isJson ? await response.json().catch(() => null) : await response.text().catch(() => "");

  if (isJson && payload && !path.startsWith("/i18n/")) {
    watchIncomingPayload(payload);
  }

  if (!response.ok) {
    const errObj = payload && typeof payload === "object" && "error" in payload
      ? (payload as { error?: { message?: string; code?: string; details?: Record<string, unknown> }; request_id?: string })
      : null;
    throw new ApiError(
      errObj?.error?.message ||
        (typeof payload === "string" && payload) ||
        `Request failed (${response.status})`,
      response.status,
      errObj?.error?.code || "http_error",
      errObj?.error?.details,
      errObj?.request_id
    );
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, query?: RequestOptions["query"]) =>
    apiRequest<T>(path, { method: "GET", query }),
  post: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    apiRequest<T>(path, { method: "POST", body, query }),
  put: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    apiRequest<T>(path, { method: "PUT", body, query }),
  patch: <T>(path: string, body?: unknown, query?: RequestOptions["query"]) =>
    apiRequest<T>(path, { method: "PATCH", body, query }),
  delete: <T>(path: string, query?: RequestOptions["query"]) =>
    apiRequest<T>(path, { method: "DELETE", query }),
};
