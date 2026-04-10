"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import StoredProfilesPanel from "@/components/StoredProfilesPanel";

function getToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)vkorni_token=([^;]+)/);
  return match ? match[1] : "";
}

function clearToken() {
  document.cookie = "vkorni_token=; path=/; max-age=0";
}

export default function AdminPage() {
  const router = useRouter();
  const [cpCurrent, setCpCurrent] = useState("");
  const [cpNew, setCpNew] = useState("");
  const [cpConfirm, setCpConfirm] = useState("");
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const [busy, setBusy] = useState(false);

  function logout() {
    clearToken();
    router.push("/admin/login");
  }

  async function handleChangePassword(e: React.FormEvent) {
    e.preventDefault();
    setResult(null);
    if (cpNew !== cpConfirm) {
      setResult({ ok: false, msg: "Новые пароли не совпадают" });
      return;
    }
    setBusy(true);
    try {
      await api.adminChangePassword(getToken(), cpCurrent, cpNew);
      setResult({ ok: true, msg: "Пароль изменен" });
      setCpCurrent(""); setCpNew(""); setCpConfirm("");
    } catch (err) {
      setResult({ ok: false, msg: err instanceof Error ? err.message : "Ошибка" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen px-5 py-8 md:px-8 md:py-10">
      <div className="mx-auto max-w-7xl">
        <div className="mb-8 flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-[0.3em] text-ink/40">Vkorni</span>
            <h1 className="mt-1 text-3xl font-semibold text-ink" style={{ fontFamily: "var(--font-display)" }}>
              Администрирование
            </h1>
            <p className="mt-2 max-w-3xl text-sm text-ink/55">
              Управление доступом и отдельный архив уже отправленных профилей, сохраненных в базе данных сервера.
            </p>
          </div>
          <div className="flex items-center gap-4">
            <a href="/" className="text-xs text-ink/40 hover:text-ink/70 transition-colors">
              ← Приложение
            </a>
            <button onClick={logout} className="text-xs text-red-400 hover:text-red-600 transition-colors">
              Выйти
            </button>
          </div>
        </div>

        <div className="grid gap-6 xl:grid-cols-[320px,minmax(0,1fr)]">
          <div className="space-y-6">
            <div className="rounded-[28px] border border-ink/10 bg-white/75 p-6 shadow-soft backdrop-blur">
              <div className="mb-5">
                <span className="text-[11px] font-bold uppercase tracking-[0.28em] text-ember/65">Доступ</span>
                <h2 className="mt-2 text-lg font-semibold text-ink">Смена пароля</h2>
                <p className="mt-2 text-sm text-ink/55">
                  Этот блок отделен от архива профилей, чтобы управление экспортами оставалось наглядным.
                </p>
              </div>
              <form onSubmit={handleChangePassword} className="flex flex-col gap-3">
                <input
                  type="password"
                  placeholder="Текущий пароль"
                  value={cpCurrent}
                  onChange={(e) => setCpCurrent(e.target.value)}
                  required
                  className="w-full rounded-xl border border-ink/15 bg-white/60 px-4 py-2.5 text-sm text-ink placeholder:text-ink/35 focus:outline-none focus:ring-2 focus:ring-ink/20"
                />
                <input
                  type="password"
                  placeholder="Новый пароль (минимум 8 символов)"
                  value={cpNew}
                  onChange={(e) => setCpNew(e.target.value)}
                  required
                  className="w-full rounded-xl border border-ink/15 bg-white/60 px-4 py-2.5 text-sm text-ink placeholder:text-ink/35 focus:outline-none focus:ring-2 focus:ring-ink/20"
                />
                <input
                  type="password"
                  placeholder="Подтвердить новый пароль"
                  value={cpConfirm}
                  onChange={(e) => setCpConfirm(e.target.value)}
                  required
                  className="w-full rounded-xl border border-ink/15 bg-white/60 px-4 py-2.5 text-sm text-ink placeholder:text-ink/35 focus:outline-none focus:ring-2 focus:ring-ink/20"
                />
                {result && (
                  <p className={`rounded-lg px-3 py-2 text-xs ${result.ok ? "bg-emerald-50 text-emerald-600" : "bg-red-50 text-red-500"}`}>
                    {result.msg}
                  </p>
                )}
                <button
                  type="submit"
                  disabled={busy}
                  className="rounded-xl bg-ink px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-ink/80 disabled:opacity-50"
                >
                  {busy ? "…" : "Сменить пароль"}
                </button>
              </form>
            </div>
          </div>

          <StoredProfilesPanel />
        </div>
      </div>
    </div>
  );
}
