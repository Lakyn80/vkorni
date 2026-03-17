"use client";

type Props = {
  input: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSubmit: (names: string[]) => void;
};

function parseNames(input: string): string[] {
  return input
    .split(/[\n,]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export function GenerateForm({ input, busy, onChange, onSubmit }: Props) {
  const names = parseNames(input);
  const isBatch = names.length > 1;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (names.length > 0) onSubmit(names);
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <div className="relative">
        <textarea
          value={input}
          onChange={(e) => onChange(e.target.value)}
          placeholder={"Владимир Высоцкий\nЛев Яшин\nВиктор Цой..."}
          rows={isBatch ? Math.min(names.length + 1, 8) : 2}
          className="w-full rounded-2xl border border-ink/12 bg-white px-4 py-3.5 text-sm text-ink shadow-sm placeholder:text-ink/30 focus:border-lake/50 focus:outline-none focus:ring-2 focus:ring-lake/10 resize-none"
        />
      </div>

      {isBatch && (
        <p className="text-xs text-ink/40 px-1">
          {names.length} имён — пакетная обработка
        </p>
      )}

      <button
        type="submit"
        disabled={busy || names.length === 0}
        className="rounded-xl bg-ink px-4 py-2.5 text-xs font-semibold text-white transition-opacity disabled:opacity-40"
      >
        {busy ? (
          <span className="flex items-center justify-center gap-1.5">
            <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
            {isBatch ? "Запуск пакета..." : "Генерация..."}
          </span>
        ) : isBatch ? `Создать пакет (${names.length})` : "Создать"}
      </button>
    </form>
  );
}
