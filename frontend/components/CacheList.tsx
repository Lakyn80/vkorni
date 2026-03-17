"use client";

type Props = {
  names: string[];
  loading: boolean;
  error: string;
  onSelect: (name: string) => void;
  onRefresh: () => void;
  onDelete: (name: string) => void;
  onDeleteAll: () => void;
};

export function CacheList({ names, loading, error, onSelect, onRefresh, onDelete, onDeleteAll }: Props) {
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
        <div className="flex max-h-64 flex-col gap-1 overflow-y-auto">
          {names.map((name) => (
            <div
              key={name}
              className="group flex items-center justify-between rounded-xl border border-ink/8 bg-white px-3 py-2.5 hover:border-ink/20 hover:bg-mist/50 transition-all"
            >
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
                className="ml-2 flex h-5 w-5 items-center justify-center rounded-full text-ink/20 opacity-0 transition-all hover:bg-red-50 hover:text-red-400 group-hover:opacity-100"
                title="Удалить"
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
