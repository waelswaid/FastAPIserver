import { decodeJwt, type DecodedJwt } from "./jwt";

export type TokenEntry = {
  id: number;
  capturedAt: number;
  token: string;
  decoded: DecodedJwt | null;
  decodeError?: string;
};

const STORAGE_KEY = "dev_client_token_log";
const MAX_ENTRIES = 50;

type Subscriber = () => void;
const subscribers = new Set<Subscriber>();

type PersistedShape = {
  entries: TokenEntry[];
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
    // sessionStorage may be unavailable; keep in-memory log only
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

export function append(token: string): TokenEntry {
  let decoded: DecodedJwt | null = null;
  let decodeError: string | undefined;
  try {
    decoded = decodeJwt(token);
  } catch (err) {
    decodeError = err instanceof Error ? err.message : String(err);
  }

  const entry: TokenEntry = {
    id: state.nextId,
    capturedAt: Date.now(),
    token,
    decoded,
    ...(decodeError ? { decodeError } : {}),
  };
  state.nextId += 1;
  state.entries.push(entry);
  if (state.entries.length > MAX_ENTRIES) {
    state.entries.splice(0, state.entries.length - MAX_ENTRIES);
  }
  persist();
  notify();
  return entry;
}

export function getAll(): TokenEntry[] {
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
