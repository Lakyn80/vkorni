"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const data = await api.adminLogin(username, password);
      // Store token in cookie (readable by Next.js middleware)
      document.cookie = `vkorni_token=${data.access_token}; path=/; SameSite=Lax; max-age=${60 * 60}`;
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Neplatné přihlašovací údaje");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <span className="text-xs font-bold uppercase tracking-[0.3em] text-ink/40">Vkorni</span>
          <h1 className="mt-2 text-2xl font-semibold text-ink" style={{ fontFamily: "var(--font-display)" }}>
            Přihlášení
          </h1>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="text"
            placeholder="Uživatelské jméno"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            autoFocus
            className="w-full rounded-xl border border-ink/15 bg-white/60 px-4 py-3 text-sm text-ink placeholder:text-ink/35 focus:outline-none focus:ring-2 focus:ring-ink/20"
          />
          <input
            type="password"
            placeholder="Heslo"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            className="w-full rounded-xl border border-ink/15 bg-white/60 px-4 py-3 text-sm text-ink placeholder:text-ink/35 focus:outline-none focus:ring-2 focus:ring-ink/20"
          />

          {error && (
            <p className="rounded-lg bg-red-50 px-3 py-2 text-xs text-red-500">{error}</p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="rounded-xl bg-ink px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-ink/80 disabled:opacity-50"
          >
            {busy ? "Přihlašování…" : "Přihlásit se"}
          </button>
        </form>
      </div>
    </div>
  );
}
