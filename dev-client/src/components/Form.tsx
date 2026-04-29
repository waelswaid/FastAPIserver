import { useState, useRef, type FormEvent, type ReactNode } from "react";
import { type ApiResponse } from "../api";
import Result from "./Result";

type Props = {
  title: string;
  onSubmit: (values: Record<string, string>) => Promise<ApiResponse>;
  children: ReactNode;
  submitLabel?: string;
};

export default function Form({ title, onSubmit, children, submitLabel = "Submit" }: Props) {
  const [result, setResult] = useState<ApiResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const formRef = useRef<HTMLFormElement>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!formRef.current) return;
    const data = new FormData(formRef.current);
    const values = Object.fromEntries(data.entries()) as Record<string, string>;
    setSubmitting(true);
    try {
      setResult(await onSubmit(values));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form ref={formRef} onSubmit={handleSubmit} className="rounded border border-gray-200 p-4">
      <h3 className="font-semibold text-sm mb-3">{title}</h3>
      <div className="space-y-2">{children}</div>
      <button
        type="submit"
        disabled={submitting}
        className="mt-3 rounded bg-gray-900 px-3 py-1.5 text-xs text-white disabled:opacity-50"
      >
        {submitting ? "..." : submitLabel}
      </button>
      <Result result={result} />
    </form>
  );
}
