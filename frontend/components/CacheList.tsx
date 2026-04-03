"use client";

import { useState } from "react";
import type { BulkExportStatus } from "@/types";

type Props = {
  names: string[];
  loading: boolean;
  error: string;
  onSelect: (name: string) => void;
  onRefresh: () => void;
  onDelete: (name: string) => void;
  onDeleteAll: () => void;
  onBulkExport: (names: string[]) => void;
  bulkExport: BulkExportStatus | null;
  bulkExporting: boolean;
};

export function CacheList({ names, loading, error, onSelect, onRefresh, onDelete, onDeleteAll, onBulkExport, bulkExport, bulkExporting }: Props) {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const allSelected = names.length > 0 && selected.size === names.length;

  function toggleOne(name: string) {
    setSelected(prev => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }

  function toggleAll() {
    setSelected(allSelected ? new Set() : new Set(names));
  }

  function handleExport() {
    const toExport = selected.size > 0 ? [...selected] : names;
    onBulkExport(toExport);
  }

  const exportCount = selected.size > 0 ? selected.size : names.length;

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wider text-ink/40">
          Сохранённые ({names.length})
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={onRefresh}
            disabled={loading}
            className="text-xs text-ink/40 hover:text-ink/70 transition-colors disabled:opacity-30"
          >
            ↻ Обновить
          </button>
          {names.length > 0 && (
            <>
              <span className="text-ink/20">·</span>
              <button
                onClick={() => confirm("Удалить все профили?") && onDeleteAll()}
                disabled={loading}
                className="text-xs text-red-400 hover:text-red-500 transition-colors disabled:opacity-30"
              >
                Удалить все
              </button>
            </>
          )}
        </div>
      </div>

      {error && (
        <p className="rounded-xl bg-red-50 px-3 py-2 text-xs text-red-500">{error}</p>
      )}

      {names.length === 0 ? (
        <p className="text-xs text-ink/30">Пока пусто — создайте первый профиль</p>
      ) : (
        <>
          {/* Select all row */}
          <div className="flex items-center justify-between rounded-xl border border-ink/8 bg-mist/30 px-3 py-2">
            <label className="flex items-center gap-2 cursor-pointer text-xs text-ink/60">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                className="rounded"
              />
              Выбрать все
            </label>
            <button
              onClick={handleExport}
              disabled={bulkExporting || loading}
              className="text-xs font-medium text-emerald-600 hover:text-emerald-700 disabled:opacity-40 transition-colors"
            >
              {bulkExporting ? "Отправка..." : `→ vkorni.com (${exportCount})`}
            </button>
          </div>

          <div className="flex max-h-64 flex-col gap-1 overflow-y-auto">
            {names.map((name) => (
              <div
                key={name}
                className="group flex items-center gap-2 rounded-xl border border-ink/8 bg-white px-3 py-2.5 hover:border-ink/20 hover:bg-mist/50 transition-all"
              >
                <input
                  type="checkbox"
                  checked={selected.has(name)}
                  onChange={() => toggleOne(name)}
                  className="rounded shrink-0"
                  onClick={e => e.stopPropagation()}
                />
                <button
                  className="flex-1 text-left text-sm font-medium text-ink/80 hover:text-ink"
                  onClick={() => onSelect(name)}
                  disabled={loading}
                >
                  {name}
                </button>
                <button
                  onClick={() => onDelete(name)}
                  disabled={loading}
                  className="ml-1 flex h-5 w-5 items-center justify-center rounded-full text-ink/20 opacity-0 transition-all hover:bg-red-50 hover:text-red-400 group-hover:opacity-100"
                  title="Удалить"
                >
                  ×
                </button>
              </div>
            ))}
          </div>

          {/* Bulk export status */}
          {bulkExport && (
            <div className="rounded-xl border border-ink/8 bg-white p-3 text-xs flex flex-col gap-2">
              <div className="flex items-center justify-between font-semibold text-ink/70">
                <span>Экспорт на vkorni.com</span>
                <span>{bulkExport.done + bulkExport.failed}/{bulkExport.total}</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-ink/8 overflow-hidden">
                <div
                  className="h-full rounded-full bg-emerald-500 transition-all"
                  style={{ width: `${((bulkExport.done + bulkExport.failed) / bulkExport.total) * 100}%` }}
                />
              </div>
              <div className="flex flex-col gap-1 max-h-32 overflow-y-auto">
                {bulkExport.results.map(r => (
                  <div key={r.name} className="flex items-center justify-between gap-2">
                    <span className="truncate text-ink/60">{r.name}</span>
                    {r.status === "done" && r.url ? (
                      <a href={r.url} target="_blank" rel="noreferrer" className="shrink-0 text-emerald-600 hover:underline">✓ OK</a>
                    ) : r.status === "failed" ? (
                      <span className="shrink-0 text-red-400" title={r.error ?? ""}>✗ Ошибка</span>
                    ) : r.status === "running" ? (
                      <span className="shrink-0 text-blue-400">⟳</span>
                    ) : r.status === "retrying" ? (
                      <span className="shrink-0 text-amber-500" title={r.error ?? ""}>↻</span>
                    ) : (
                      <span className="shrink-0 text-ink/30">…</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
