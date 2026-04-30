import { useEffect, useMemo, useState } from "react";
import { getToken, subscribe as subscribeAuth } from "../../auth";
import { request, type ApiResponse } from "../../api";
import {
  clear,
  getAll,
  subscribe as subscribeTokens,
  type TokenEntry,
} from "../../lib/tokenLog";
import { formatTime, truncateMiddle } from "../../lib/jwt";

function fmtTime(ms: number): string {
  const d = new Date(ms);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const mss = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${mss}`;
}

function expStatus(exp: unknown, nowSec: number): { text: string; cls: string } {
  if (typeof exp !== "number") return { text: "—", cls: "text-gray-500" };
  const remaining = exp - nowSec;
  if (remaining > 0) return { text: `${remaining}s left`, cls: "text-green-700" };
  return { text: "expired", cls: "text-red-700" };
}

function readClaim(payload: Record<string, unknown> | undefined, key: string): string {
  if (!payload) return "";
  const v = payload[key];
  if (typeof v === "string") return v;
  if (typeof v === "number" || typeof v === "boolean") return String(v);
  return "";
}

export default function Token() {
  const [entries, setEntries] = useState<TokenEntry[]>(getAll());
  const [activeToken, setActiveToken] = useState<string | null>(getToken());
  const [nowSec, setNowSec] = useState<number>(() => Math.floor(Date.now() / 1000));
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    const unsub = subscribeTokens(() => setEntries(getAll()));
    return unsub;
  }, []);

  useEffect(() => {
    const unsub = subscribeAuth(() => setActiveToken(getToken()));
    return unsub;
  }, []);

  useEffect(() => {
    const t = setInterval(() => setNowSec(Math.floor(Date.now() / 1000)), 1000);
    return () => clearInterval(t);
  }, []);

  const ordered = useMemo(() => entries.slice().reverse(), [entries]);

  return (
    <div className="space-y-3">
      <div className="flex items-center">
        <button
          type="button"
          onClick={() => {
            clear();
            setExpandedId(null);
          }}
          className="ml-auto text-xs underline text-gray-600"
        >
          Clear
        </button>
      </div>

      {ordered.length === 0 ? (
        <p className="text-sm text-gray-600">
          No tokens captured yet — sign in via the Public tab.
        </p>
      ) : (
        <div className="rounded border border-gray-200 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-2 py-1 font-medium">captured</th>
                <th className="text-left px-2 py-1 font-medium">email</th>
                <th className="text-left px-2 py-1 font-medium">role</th>
                <th className="text-left px-2 py-1 font-medium">exp</th>
                <th className="text-left px-2 py-1 font-medium">jti</th>
              </tr>
            </thead>
            <tbody>
              {ordered.map((entry) => (
                <TokenRow
                  key={entry.id}
                  entry={entry}
                  active={entry.token === activeToken}
                  expanded={expandedId === entry.id}
                  nowSec={nowSec}
                  onToggle={() => setExpandedId((cur) => (cur === entry.id ? null : entry.id))}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function TokenRow({
  entry,
  active,
  expanded,
  nowSec,
  onToggle,
}: {
  entry: TokenEntry;
  active: boolean;
  expanded: boolean;
  nowSec: number;
  onToggle: () => void;
}) {
  const payload = entry.decoded?.payload;
  const email = readClaim(payload, "email");
  const role = readClaim(payload, "role");
  const jti = readClaim(payload, "jti");
  const exp = expStatus(payload?.exp, nowSec);

  const rowCls = `border-t border-gray-100 cursor-pointer hover:bg-gray-50 ${
    active ? "bg-blue-50 hover:bg-blue-100" : ""
  }`;

  return (
    <>
      <tr onClick={onToggle} className={rowCls}>
        <td className="px-2 py-1 font-mono">
          {fmtTime(entry.capturedAt)}
          {active && (
            <span className="ml-2 inline-block rounded bg-blue-600 px-1.5 py-0.5 text-[10px] font-medium text-white">
              active
            </span>
          )}
        </td>
        <td className="px-2 py-1 font-mono break-all">{email}</td>
        <td className="px-2 py-1 font-mono">{role}</td>
        <td className={`px-2 py-1 font-mono ${exp.cls}`}>{exp.text}</td>
        <td className="px-2 py-1 font-mono">{jti ? truncateMiddle(jti, 8, 4) : ""}</td>
      </tr>
      {expanded && (
        <tr className="border-t border-gray-100 bg-gray-50">
          <td colSpan={5} className="px-2 py-2">
            <TokenDetail entry={entry} active={active} />
          </td>
        </tr>
      )}
    </>
  );
}

function TokenDetail({ entry, active }: { entry: TokenEntry; active: boolean }) {
  const [showRaw, setShowRaw] = useState(false);
  const [serverView, setServerView] = useState<ApiResponse | null>(null);
  const [validating, setValidating] = useState(false);

  if (entry.decodeError) {
    return (
      <div className="rounded border border-red-200 bg-red-50 p-3 text-xs text-red-800">
        Token is malformed: {entry.decodeError}
      </div>
    );
  }

  const decoded = entry.decoded;
  if (!decoded) {
    return <div className="text-xs text-gray-600">No decoded payload available.</div>;
  }

  async function validate() {
    setValidating(true);
    try {
      setServerView(await request("GET", "/api/auth/validate-token"));
    } finally {
      setValidating(false);
    }
  }

  return (
    <div className="space-y-3">
      <div>
        <div className="text-xs font-medium mb-1">Header</div>
        <pre className="text-xs bg-white border border-gray-200 rounded p-2 overflow-x-auto">
          {JSON.stringify(decoded.header, null, 2)}
        </pre>
      </div>

      <div>
        <div className="text-xs font-medium mb-1">Payload</div>
        <table className="text-xs w-full bg-white border border-gray-200 rounded">
          <tbody>
            {Object.entries(decoded.payload).map(([k, v]) => (
              <tr key={k} className="border-b border-gray-100 last:border-b-0">
                <td className="py-1 px-2 font-medium align-top">{k}</td>
                <td className="py-1 px-2 align-top break-all">
                  {(k === "exp" || k === "iat" || k === "nbf") && typeof v === "number"
                    ? `${v} (${formatTime(v)})`
                    : typeof v === "object"
                      ? JSON.stringify(v)
                      : String(v)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div>
        <div className="text-xs font-medium mb-1">
          Raw token
          <button
            type="button"
            className="ml-2 text-xs underline text-gray-600 font-normal"
            onClick={() => setShowRaw((v) => !v)}
          >
            {showRaw ? "hide" : "show"}
          </button>
        </div>
        <pre className="text-xs bg-white border border-gray-200 rounded p-2 overflow-x-auto break-all whitespace-pre-wrap">
          {showRaw ? entry.token : truncateMiddle(entry.token)}
        </pre>
      </div>

      {active && (
        <div>
          <div className="text-xs font-medium mb-1">Validate against backend</div>
          <button
            type="button"
            onClick={validate}
            disabled={validating}
            className="rounded bg-gray-900 px-3 py-1.5 text-xs text-white disabled:opacity-50"
          >
            {validating ? "..." : "GET /api/auth/validate-token"}
          </button>
          {serverView && (
            <pre
              className={`mt-2 text-xs bg-white border border-gray-200 rounded p-2 overflow-x-auto ${
                serverView.status >= 200 && serverView.status < 300
                  ? "text-green-700"
                  : "text-amber-700"
              }`}
            >
              {serverView.error
                ? `network error: ${serverView.error}`
                : `${serverView.status}\n${JSON.stringify(serverView.body, null, 2)}`}
            </pre>
          )}
        </div>
      )}
    </div>
  );
}
