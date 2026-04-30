import { append as logToken } from "./lib/tokenLog";

const STORAGE_KEY = "dev_client_access_token";

type Subscriber = () => void;
const subscribers = new Set<Subscriber>();

function notify(): void {
  for (const cb of subscribers) {
    try {
      cb();
    } catch {
      // subscriber errors must not break other subscribers
    }
  }
}

export function getToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
  logToken(token);
  notify();
}

export function clearToken(): void {
  localStorage.removeItem(STORAGE_KEY);
  notify();
}

export function subscribe(cb: Subscriber): () => void {
  subscribers.add(cb);
  return () => {
    subscribers.delete(cb);
  };
}
