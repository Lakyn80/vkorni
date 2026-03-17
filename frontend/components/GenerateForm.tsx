"use client";

type Props = {
  input: string;
  busy: boolean;
  onChange: (value: string) => void;
  onSubmit: () => void;
};

export function GenerateForm({ input, busy, onChange, onSubmit }: Props) {
  return (
    <form onSubmit={(e) => { e.preventDefault(); onSubmit(); }} className="flex flex-col gap-3">
      <div className="relative">
        <input
          type="text"
          value={input}
          onChange={(e) => onChange(e.target.value)}
          placeholder="Владимир Высоцкий..."
          className="w-full rounded-2xl border border-ink/12 bg-white px-4 py-3.5 pr-32 text-sm text-ink shadow-sm placeholder:text-ink/30 focus:border-lake/50 focus:outline-none focus:ring-2 focus:ring-lake/10"
        />
        <button
          type="submit"
          disabled={busy || !input.trim()}
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-xl bg-ink px-4 py-2 text-xs font-semibold text-white transition-opacity disabled:opacity-40"
        >
          {busy ? (
            <span className="flex items-center gap-1.5">
              <span className="h-3 w-3 animate-spin rounded-full border-2 border-white/30 border-t-white" />
              Генерация
            </span>
          ) : "Создать"}
        </button>
      </div>
    </form>
  );
}
