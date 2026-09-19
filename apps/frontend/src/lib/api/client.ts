import { env } from "$env/dynamic/public";

/** Base URL of the FastAPI backend. */
export const API_BASE = env.PUBLIC_API_URL ?? "http://localhost:8000";
export const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  status: number;
  code: string;
  detail: unknown;
  constructor(status: number, code: string, message: string, detail?: unknown) {
    super(message);
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

type FetchOpts = Omit<RequestInit, "body"> & { body?: unknown };

async function request<T>(path: string, opts: FetchOpts = {}): Promise<T> {
  const { body, headers, ...rest } = opts;
  const isForm = body instanceof FormData;
  const res = await fetch(`${API_BASE}${API_PREFIX}${path}`, {
    ...rest,
    credentials: "include",
    headers: {
      ...(isForm ? {} : { "Content-Type": "application/json" }),
      ...(headers ?? {}),
    },
    body: isForm ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 204) return undefined as T;

  const text = await res.text();
  const data = text ? safeJson(text) : null;

  if (!res.ok) {
    const err = (data as { error?: { code: string; message: string; detail?: unknown } })?.error;
    throw new ApiError(
      res.status,
      err?.code ?? "error",
      err?.message ?? `Request failed (${res.status})`,
      err?.detail,
    );
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export const api = {
  get: <T>(path: string, opts?: FetchOpts) => request<T>(path, { ...opts, method: "GET" }),
  post: <T>(path: string, body?: unknown, opts?: FetchOpts) =>
    request<T>(path, { ...opts, method: "POST", body }),
  put: <T>(path: string, body?: unknown, opts?: FetchOpts) =>
    request<T>(path, { ...opts, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, opts?: FetchOpts) =>
    request<T>(path, { ...opts, method: "PATCH", body }),
  delete: <T>(path: string, opts?: FetchOpts) => request<T>(path, { ...opts, method: "DELETE" }),
};

export function wsUrl(path: string): string {
  const base = API_BASE.replace(/^http/, "ws");
  return `${base}${path}`;
}
