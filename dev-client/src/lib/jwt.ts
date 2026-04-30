export type DecodedJwt = {
  header: Record<string, unknown>;
  payload: Record<string, unknown>;
};

export function base64UrlDecode(input: string): string {
  const padded = input.replace(/-/g, "+").replace(/_/g, "/");
  const pad = padded.length % 4 === 0 ? "" : "=".repeat(4 - (padded.length % 4));
  return atob(padded + pad);
}

export function decodeJwt(token: string): DecodedJwt {
  const parts = token.split(".");
  if (parts.length !== 3) throw new Error("token must have 3 segments");
  const header = JSON.parse(base64UrlDecode(parts[0])) as Record<string, unknown>;
  const payload = JSON.parse(base64UrlDecode(parts[1])) as Record<string, unknown>;
  return { header, payload };
}

export function truncateMiddle(s: string, head = 8, tail = 8): string {
  if (s.length <= head + tail + 3) return s;
  return `${s.slice(0, head)}...${s.slice(-tail)}`;
}

export function formatTime(epochSeconds: unknown): string {
  if (typeof epochSeconds !== "number") return String(epochSeconds);
  return new Date(epochSeconds * 1000).toISOString();
}
