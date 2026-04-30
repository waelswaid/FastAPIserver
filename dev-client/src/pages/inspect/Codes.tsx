import { useCallback, useEffect, useState } from "react";
import { request } from "../../api";

type DevCode = {
  email_type: string;
  recipient: string;
  code: string;
  link: string;
  captured_at: number;
};

const REFRESH_MS = 3000;

function fmtTime(epochSeconds: number): string {
  const d = new Date(epochSeconds * 1000);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  return `${hh}:${mm}:${ss}`;
}

function typeBadge(t: string): string {
  const base = "inline-block rounded px-2 py-0.5 text-[10px] font-medium";
  if (t === "email_verification") return `${base} bg-blue-100 text-blue-800`;
  if (t === "password_reset") return `${base} bg-amber-100 text-amber-800`;
  if (t === "invite") return `${base} bg-purple-100 text-purple-800`;
  return `${base} bg-gray-100 text-gray-800`;
}

function truncateMiddle(s: string, head = 10, tail = 6): string {
  if (s.length <= head + tail + 3) return s;
  return `${s.slice(0, head)}...${s.slice(-tail)}`;
}

async function copyToClipboard(text: string): Promise<void> {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // ignore — copy is best-effort UX
  }
}

export default function Codes() {
  const [codes, setCodes] = useState<DevCode[]>([]);
  const [paused, setPaused] = useState(false);
  const [disabled, setDisabled] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const fetchCodes = useCallback(async () => {
    const res = await request<DevCode[]>("GET", "/api/dev/codes");
    if (res.status === 404) {
      setDisabled(true);
      return;
    }
    if (res.status === 200 && Array.isArray(res.body)) {
      setDisabled(false);
      setCodes(res.body);
    }
  }, []);

  useEffect(() => {
    if (disabled) return;
    // Defer the initial fetch past the synchronous render so setState happens
    // outside the effect body (react-hooks/set-state-in-effect).
    const initial = setTimeout(fetchCodes, 0);
    return () => clearTimeout(initial);
  }, [disabled, fetchCodes]);

  useEffect(() => {
    if (paused || disabled) return;
    const t = setInterval(fetchCodes, REFRESH_MS);
    return () => clearInterval(t);
  }, [paused, disabled, fetchCodes]);

  async function handleClear() {
    await request("DELETE", "/api/dev/codes");
    fetchCodes();
  }

  async function handleCopy(value: string, key: string) {
    await copyToClipboard(value);
    setCopied(key);
    setTimeout(() => setCopied((cur) => (cur === key ? null : cur)), 1200);
  }

  if (disabled) {
    return (
      <div className="rounded border border-amber-200 bg-amber-50 p-4 text-xs text-amber-800">
        Dev-codes endpoint not available — set <code>ENVIRONMENT=development</code> and restart the
        backend.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => setPaused((p) => !p)}
          className="px-2 py-1 text-xs rounded border bg-white text-gray-700 border-gray-300"
        >
          {paused ? "Resume" : "Pause"}
        </button>
        <span className="text-xs text-gray-500">
          {paused ? "auto-refresh paused" : `auto-refresh every ${REFRESH_MS / 1000}s`}
        </span>
        <button
          type="button"
          onClick={handleClear}
          className="ml-auto text-xs underline text-gray-600"
        >
          Clear
        </button>
      </div>

      {codes.length === 0 ? (
        <p className="text-sm text-gray-600">
          No codes captured. Trigger Register, Forgot password, or Admin → Invite from the other
          tabs.
        </p>
      ) : (
        <div className="rounded border border-gray-200 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-2 py-1 font-medium">time</th>
                <th className="text-left px-2 py-1 font-medium">type</th>
                <th className="text-left px-2 py-1 font-medium">recipient</th>
                <th className="text-left px-2 py-1 font-medium">code</th>
                <th className="text-left px-2 py-1 font-medium">link</th>
              </tr>
            </thead>
            <tbody>
              {codes.map((c, i) => {
                const codeKey = `code-${i}`;
                const linkKey = `link-${i}`;
                return (
                  <tr key={`${c.captured_at}-${i}`} className="border-t border-gray-100">
                    <td className="px-2 py-1 font-mono">{fmtTime(c.captured_at)}</td>
                    <td className="px-2 py-1">
                      <span className={typeBadge(c.email_type)}>{c.email_type}</span>
                    </td>
                    <td className="px-2 py-1 font-mono break-all">{c.recipient}</td>
                    <td className="px-2 py-1 font-mono">
                      <button
                        type="button"
                        onClick={() => handleCopy(c.code, codeKey)}
                        className="underline text-gray-700 hover:text-gray-900"
                        title="copy code"
                      >
                        {truncateMiddle(c.code)}
                      </button>
                      {copied === codeKey && <span className="ml-2 text-green-700">copied</span>}
                    </td>
                    <td className="px-2 py-1 font-mono break-all">
                      <button
                        type="button"
                        onClick={() => handleCopy(c.link, linkKey)}
                        className="underline text-gray-700 hover:text-gray-900"
                        title="copy link"
                      >
                        {truncateMiddle(c.link, 20, 8)}
                      </button>
                      {copied === linkKey && <span className="ml-2 text-green-700">copied</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
