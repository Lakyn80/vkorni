"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

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
      setResult({ ok: false, msg: "Nová hesla se neshodují" });
      return;
    }
    setBusy(true);
    try {
      await api.adminChangePassword(getToken(), cpCurrent, cpNew);
      setResult({ ok: true, msg: "Heslo bylo změněno" });
      setCpCurrent(""); setCpNew(""); setCpConfirm("");
    } catch (err) {
      setResult({ ok: false, msg: err instanceof Error ? err.message : "Chyba" });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen px-6 py-10">
      <div className="mx-auto max-w-lg">
        <div className="mb-8 flex items-center justify-between">
          <div>
            <span className="text-xs font-bold uppercase tracking-[0.3em] text-ink/40">Vkorni</span>
            <h1 className="mt-1 text-xl font-semibold text-ink" style={{ fontFamily: "var(--font-display)" }}>
              Administrace
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <a href="/" className="text-xs text-ink/40 hover:text-ink/70 transition-colors">
              ← Aplikace
            </a>
            <button onClick={logout} className="text-xs text-red-400 hover:text-red-600 transition-colors">
              Odhlásit
            </button>
          </div>
        </div>

        <div className="rounded-2xl border border-ink/10 bg-white/60 p-6">
          <h2 className="mb-4 text-sm font-semibold text-ink">Změna hesla</h2>
          <form onSubmit={handleChangePassword} className="flex flex-col gap-3">
            <input
              type="password"
              placeholder="Stávající heslo"
              value={cpCurrent}
              onChange={(e) => setCpCurrent(e.target.value)}
              required
              className="w-full rounded-xl border border-ink/15 bg-white/60 px-4 py-2.5 text-sm text-ink placeholder:text-ink/35 focus:outline-none focus:ring-2 focus:ring-ink/20"
            />
            <input
              type="password"
              placeholder="Nové heslo (min. 8 znaků)"
              value={cpNew}
              onChange={(e) => setCpNew(e.target.value)}
              required
              className="w-full rounded-xl border border-ink/15 bg-white/60 px-4 py-2.5 text-sm text-ink placeholder:text-ink/35 focus:outline-none focus:ring-2 focus:ring-ink/20"
            />
            <input
              type="password"
              placeholder="Potvrdit nové heslo"
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
              {busy ? "…" : "Změnit heslo"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
