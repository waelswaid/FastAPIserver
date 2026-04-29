import type { ApiResponse } from "../api";

type Props = {
  result: ApiResponse | null;
};

export default function Result({ result }: Props) {
  if (result === null) return null;

  const ok = result.status >= 200 && result.status < 300;
  const statusColor = ok ? "text-green-700" : result.status === 0 ? "text-red-700" : "text-amber-700";

  return (
    <pre className={`mt-2 rounded border border-gray-200 bg-gray-50 p-2 text-xs overflow-x-auto ${statusColor}`}>
      {result.error
        ? `network error: ${result.error}`
        : `${result.status}\n${JSON.stringify(result.body, null, 2)}`}
    </pre>
  );
}
