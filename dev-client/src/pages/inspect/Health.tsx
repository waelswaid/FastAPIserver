import { useState } from "react";
import { request, type ApiResponse } from "../../api";

type HealthCheck = { status: "up" | "down"; detail?: string };
type HealthBody = {
  status?: "healthy" | "degraded" | "unhealthy";
  checks?: Record<string, HealthCheck>;
};

const dot = (up: boolean) =>
  `inline-block w-2 h-2 rounded-full mr-2 ${up ? "bg-green-500" : "bg-red-500"}`;

const badge = (status?: string) => {
  const cls =
    status === "healthy"
      ? "bg-green-100 text-green-800"
      : status === "degraded"
        ? "bg-amber-100 text-amber-800"
        : "bg-red-100 text-red-800";
  return `inline-block rounded px-2 py-0.5 text-xs font-medium ${cls}`;
};

export default function Health() {
  const [result, setResult] = useState<ApiResponse<HealthBody> | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    try {
      setResult(await request<HealthBody>("GET", "/health"));
    } finally {
      setLoading(false);
    }
  }

  const body = result?.body;

  return (
    <div className="rounded border border-gray-200 p-4 max-w-xl">
      <h3 className="font-semibold text-sm mb-3">Health check</h3>
      <button
        type="button"
        onClick={run}
        disabled={loading}
        className="rounded bg-gray-900 px-3 py-1.5 text-xs text-white disabled:opacity-50"
      >
        {loading ? "..." : "GET /health"}
      </button>

      {result && (
        <div className="mt-3 space-y-2">
          {body?.status && (
            <div>
              <span className={badge(body.status)}>{body.status}</span>
            </div>
          )}
          {body?.checks &&
            Object.entries(body.checks).map(([name, c]) => (
              <div key={name} className="text-xs flex items-center">
                <span className={dot(c.status === "up")}></span>
                <span className="font-medium mr-2">{name}</span>
                <span className="text-gray-600">
                  {c.status}
                  {c.detail ? ` — ${c.detail}` : ""}
                </span>
              </div>
            ))}
          <pre className="mt-2 rounded border border-gray-200 bg-gray-50 p-2 text-xs overflow-x-auto">
            {result.error
              ? `network error: ${result.error}`
              : `${result.status}\n${JSON.stringify(result.body, null, 2)}`}
          </pre>
        </div>
      )}
    </div>
  );
}
