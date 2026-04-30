export type ActivityEntry = {
  id: number;
  startedAt: number;
  durationMs: number;
  method: string;
  path: string;
  status: number;
  requestBody: unknown;
  responseBody: unknown;
  error?: string;
  email?: string;
};

const STORAGE_KEY = "dev_client_activity_log";
const MAX_ENTRIES = 200;
const REDACT_KEYS = new Set([
  "password",
  "current_password",
  "new_password",
  "token",
  "access_token",
  "refresh_token",
]);

type Subscriber = () => void;
const subscribers = new Set<Subscriber>();

type PersistedShape = {
  entries: ActivityEntry[];
  nextId: number;
};

function loadFromStorage(): PersistedShape {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { entries: [], nextId: 1 };
    const parsed = JSON.parse(raw) as Partial<PersistedShape>;
    const entries = Array.isArray(parsed.entries) ? parsed.entries : [];
    const nextId = typeof parsed.nextId === "number" ? parsed.nextId : entries.length + 1;
    return { entries, nextId };
  } catch {
    return { entries: [], nextId: 1 };
  }
}

const state: PersistedShape = loadFromStorage();

function persist(): void {
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch {
    // sessionStorage may be unavailable (private mode, quota); keep in-memory log only
  }
}

function notify(): void {
  for (const cb of subscribers) {
    try {
      cb();
    } catch {
      // subscriber errors must not affect others
    }
  }
}

export function redact(value: unknown): unknown {
  if (value === null || value === undefined) return value;
  if (Array.isArray(value)) return value.map((v) => redact(v));
  if (typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = REDACT_KEYS.has(k) ? "***" : redact(v);
    }
    return out;
  }
  return value;
}

export function append(entry: Omit<ActivityEntry, "id">): ActivityEntry {
  const full: ActivityEntry = {
    ...entry,
    id: state.nextId,
    requestBody: redact(entry.requestBody),
    responseBody: redact(entry.responseBody),
  };
  state.nextId += 1;
  state.entries.push(full);
  if (state.entries.length > MAX_ENTRIES) {
    state.entries.splice(0, state.entries.length - MAX_ENTRIES);
  }
  persist();
  notify();
  return full;
}

export function getAll(): ActivityEntry[] {
  return state.entries.slice();
}

export function clear(): void {
  state.entries.length = 0;
  persist();
  notify();
}

export function subscribe(cb: Subscriber): () => void {
  subscribers.add(cb);
  return () => {
    subscribers.delete(cb);
  };
}
