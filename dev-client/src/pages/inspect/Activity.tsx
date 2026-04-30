import { useEffect, useMemo, useState } from "react";
import {
  clear,
  getAll,
  subscribe,
  type ActivityEntry,
} from "../../lib/activityLog";

type StatusFilter = "all" | "2xx" | "4xx" | "5xx" | "neterr";

function statusClass(status: number): string {
  if (status === 0) return "text-red-700";
  if (status >= 200 && status < 300) return "text-green-700";
  if (status >= 400 && status < 500) return "text-amber-700";
  if (status >= 500) return "text-red-700";
  return "text-gray-700";
}

function fmtTime(ms: number): string {
  const d = new Date(ms);
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  const ss = String(d.getSeconds()).padStart(2, "0");
  const mss = String(d.getMilliseconds()).padStart(3, "0");
  return `${hh}:${mm}:${ss}.${mss}`;
}

function matchesStatus(entry: ActivityEntry, f: StatusFilter): boolean {
  if (f === "all") return true;
  if (f === "neterr") return entry.status === 0;
  if (f === "2xx") return entry.status >= 200 && entry.status < 300;
  if (f === "4xx") return entry.status >= 400 && entry.status < 500;
  if (f === "5xx") return entry.status >= 500 && entry.status < 600;
  return true;
}

export default function Activity() {
  const [entries, setEntries] = useState<ActivityEntry[]>(getAll());
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  useEffect(() => {
    const unsub = subscribe(() => setEntries(getAll()));
    return unsub;
  }, []);

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return entries
      .filter((e) => matchesStatus(e, filter))
      .filter((e) => (q ? e.path.toLowerCase().includes(q) : true))
      .slice()
      .reverse();
  }, [entries, filter, search]);

  const pillCls = (active: boolean) =>
    `px-2 py-1 text-xs rounded border ${
      active ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-700 border-gray-300"
    }`;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className={pillCls(filter === "all")} onClick={() => setFilter("all")}>
          All
        </button>
        <button type="button" className={pillCls(filter === "2xx")} onClick={() => setFilter("2xx")}>
          2xx
        </button>
        <button type="button" className={pillCls(filter === "4xx")} onClick={() => setFilter("4xx")}>
          4xx
        </button>
        <button type="button" className={pillCls(filter === "5xx")} onClick={() => setFilter("5xx")}>
          5xx
        </button>
        <button
          type="button"
          className={pillCls(filter === "neterr")}
          onClick={() => setFilter("neterr")}
        >
          net err
        </button>
        <input
          type="text"
          placeholder="search path"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="ml-2 rounded border border-gray-300 px-2 py-1 text-xs"
        />
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

      {filtered.length === 0 ? (
        <p className="text-sm text-gray-600">
          No activity yet — try a form on another tab.
        </p>
      ) : (
        <div className="rounded border border-gray-200 overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-gray-50">
              <tr>
                <th className="text-left px-2 py-1 font-medium">time</th>
                <th className="text-left px-2 py-1 font-medium">method</th>
                <th className="text-left px-2 py-1 font-medium">path</th>
                <th className="text-left px-2 py-1 font-medium">email</th>
                <th className="text-left px-2 py-1 font-medium">status</th>
                <th className="text-left px-2 py-1 font-medium">ms</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e) => (
                <ActivityRow
                  key={e.id}
                  entry={e}
                  expanded={expandedId === e.id}
                  onToggle={() => setExpandedId((cur) => (cur === e.id ? null : e.id))}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

function ActivityRow({
  entry,
  expanded,
  onToggle,
}: {
  entry: ActivityEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <>
      <tr
        onClick={onToggle}
        className="border-t border-gray-100 cursor-pointer hover:bg-gray-50"
      >
        <td className="px-2 py-1 font-mono">{fmtTime(entry.startedAt)}</td>
        <td className="px-2 py-1 font-mono">{entry.method}</td>
        <td className="px-2 py-1 font-mono break-all">{entry.path}</td>
        <td className="px-2 py-1 font-mono break-all text-gray-600">{entry.email ?? ""}</td>
        <td className={`px-2 py-1 font-mono ${statusClass(entry.status)}`}>
          {entry.status === 0 ? "ERR" : entry.status}
        </td>
        <td className="px-2 py-1 font-mono">{entry.durationMs}</td>
      </tr>
      {expanded && (
        <tr className="border-t border-gray-100 bg-gray-50">
          <td colSpan={6} className="px-2 py-2">
            {entry.email && (
              <div className="text-xs text-gray-600 mb-2">auth: {entry.email}</div>
            )}
            {entry.error && (
              <div className="text-xs text-red-700 mb-2">network error: {entry.error}</div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
              <div>
                <div className="text-xs font-medium mb-1">request body</div>
                <pre className="text-xs bg-white border border-gray-200 rounded p-2 overflow-x-auto">
                  {entry.requestBody === null
                    ? "(none)"
                    : JSON.stringify(entry.requestBody, null, 2)}
                </pre>
              </div>
              <div>
                <div className="text-xs font-medium mb-1">response body</div>
                <pre className="text-xs bg-white border border-gray-200 rounded p-2 overflow-x-auto">
                  {entry.responseBody === null
                    ? "(none)"
                    : JSON.stringify(entry.responseBody, null, 2)}
                </pre>
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}
