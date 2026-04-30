import { getToken } from "./auth";
import { append } from "./lib/activityLog";
import { decodeJwt } from "./lib/jwt";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "http://localhost:8000";

export type ApiResponse<T = unknown> = {
  status: number;
  body: T | null;
  error?: string;
};

function emailFromToken(token: string | null): string | undefined {
  if (!token) return undefined;
  try {
    const { payload } = decodeJwt(token);
    return typeof payload.email === "string" ? payload.email : undefined;
  } catch {
    return undefined;
  }
}

// Paths under /api/dev/ are dev-client infrastructure (e.g. the Codes
// sub-section's polling). They are not auth flows being traced, so we
// suppress them from the activity log to keep the trace signal clean.
function shouldLogActivity(path: string): boolean {
  return !path.startsWith("/api/dev/");
}

export async function request<T = unknown>(
  method: string,
  path: string,
  body?: unknown,
): Promise<ApiResponse<T>> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const email = emailFromToken(token);

  const init: RequestInit = {
    method,
    headers,
    credentials: "include",
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const startedAt = Date.now();

  try {
    const resp = await fetch(`${BASE_URL}${path}`, init);
    let parsed: unknown = null;
    const text = await resp.text();
    if (text) {
      try {
        parsed = JSON.parse(text);
      } catch {
        parsed = text;
      }
    }
    if (shouldLogActivity(path)) {
      append({
        startedAt,
        durationMs: Date.now() - startedAt,
        method,
        path,
        status: resp.status,
        requestBody: body ?? null,
        responseBody: parsed,
        ...(email ? { email } : {}),
      });
    }
    return { status: resp.status, body: parsed as T };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    if (shouldLogActivity(path)) {
      append({
        startedAt,
        durationMs: Date.now() - startedAt,
        method,
        path,
        status: 0,
        requestBody: body ?? null,
        responseBody: null,
        error: message,
        ...(email ? { email } : {}),
      });
    }
    return { status: 0, body: null, error: message };
  }
}
