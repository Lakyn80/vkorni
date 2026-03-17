"use client";

import type { BatchStatus } from "@/types";

type Props = {
  batch: BatchStatus;
  busy: boolean;
  onRetry: () => void;
  onClose: () => void;
};

const STATUS_ICON: Record<string, string> = {
  queued:   "⏳",
  running:  "🔄",
  done:     "✅",
  failed:   "❌",
  retrying: "🔁",
};

export function BatchPanel({ batch, busy, onRetry, onClose }: Props) {
  const finished = batch.done + batch.failed;
  const pct = batch.total > 0 ? Math.round((finished / batch.total) * 100) : 0;
  const allDone = batch.queued === 0 && batch.running === 0;

  return (
    <div className="rounded-3xl border border-ink/10 bg-white/80 p-6 shadow-sm">
      {/* Header */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-base font-semibold text-ink">Пакетная обработка</h2>
          <p className="text-xs text-ink/40 mt-0.5">
            {allDone
              ? `Завершено — ${batch.done} готово, ${batch.failed} ошибок`
              : `${finished} / ${batch.total} — обрабатывается...`}
          </p>
        </div>
        {allDone && (
          <button
            onClick={onClose}
            className="text-xs text-ink/40 hover:text-ink transition-colors"
          >
            ✕ Закрыть
          </button>
        )}
      </div>

      {/* Progress bar */}
      <div className="h-2 rounded-full bg-ink/8 mb-5 overflow-hidden">
        <div
          className="h-full rounded-full bg-emerald-500 transition-all duration-500"
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* Job list */}
      <ul className="space-y-1.5 max-h-80 overflow-y-auto pr-1">
        {batch.results.map((job) => (
          <li key={job.name} className="flex items-start gap-2 text-sm">
            <span className="shrink-0 mt-0.5">
              {job.status === "running"
                ? <span className="inline-block h-3.5 w-3.5 animate-spin rounded-full border-2 border-ink/20 border-t-ink/60 mt-0.5" />
                : STATUS_ICON[job.status] ?? "⏳"}
            </span>
            <span className={job.status === "failed" ? "text-red-500" : "text-ink/80"}>
              {job.name}
              {job.status === "failed" && job.error && (
                <span className="block text-xs text-red-400 mt-0.5">{job.error}</span>
              )}
            </span>
          </li>
        ))}
      </ul>

      {/* Retry button */}
      {allDone && batch.failed > 0 && (
        <button
          onClick={onRetry}
          disabled={busy}
          className="mt-4 rounded-xl bg-red-50 px-4 py-2 text-xs font-semibold text-red-600 hover:bg-red-100 transition-colors disabled:opacity-40"
        >
          Повторить {batch.failed} ошибки
        </button>
      )}
    </div>
  );
}
