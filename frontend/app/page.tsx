"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useCacheList } from "@/hooks/useCacheList";
import { useProfiles } from "@/hooks/useProfiles";
import { useBatch } from "@/hooks/useBatch";
import { useBulkExport } from "@/hooks/useBulkExport";
import { GenerateForm } from "@/components/GenerateForm";
import { CacheList } from "@/components/CacheList";
import { ProfileCard } from "@/components/ProfileCard";
import { BatchPanel } from "@/components/BatchPanel";

function logout(router: ReturnType<typeof useRouter>) {
  document.cookie = "vkorni_token=; path=/; max-age=0";
  router.push("/admin/login");
}

export default function Page() {
  const router = useRouter();
  const [input, setInput] = useState("");

  const { names, loading: cacheLoading, error: cacheError, refresh, addName, deleteName, deleteAll } = useCacheList();
  const { profiles, busy: profileBusy, loadingCached, generate, loadCached, regenerate, exportProfile, uploadPhoto, selectPhoto } = useProfiles(addName);
  const { batch, busy: batchBusy, startBatch, retryFailed, clearBatch } = useBatch(refresh);
  const { status: bulkExportStatus, busy: bulkExporting, startExport } = useBulkExport();

  function handleSubmit(names: string[]) {
    if (names.length === 1) {
      generate(names[0]);
    } else {
      startBatch(names);
    }
    setInput("");
  }

  const busy = profileBusy || batchBusy;
  const showBatch = batch !== null;

  return (
    <div className="min-h-screen">
      {/* Top bar */}
      <header className="border-b border-ink/8 bg-white/60 backdrop-blur-md sticky top-0 z-10">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <span className="text-xs font-bold uppercase tracking-[0.3em] text-ink/40">Vkorni</span>
            <span className="h-4 w-px bg-ink/15" />
            <span className="text-sm font-medium text-ink/70">Генератор биографий</span>
          </div>
          <div className="flex items-center gap-4">
            <a
              href="/admin"
              className="text-xs font-semibold text-ink/45 hover:text-ink/75 transition-colors"
            >
              Админ
            </a>
            <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-semibold text-emerald-600">
              ● Онлайн
            </span>
            <button
              onClick={() => logout(router)}
              className="text-xs text-ink/40 hover:text-red-500 transition-colors"
            >
              Выйти
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-10">
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-[380px_1fr]">

          {/* LEFT — controls */}
          <aside className="flex flex-col gap-6">
            <div>
              <h1 className="text-2xl font-semibold text-ink" style={{ fontFamily: "var(--font-display)" }}>
                Создать профиль
              </h1>
              <p className="mt-1 text-sm text-ink/50">
                Одно имя или список — по одному на строке
              </p>
            </div>

            <GenerateForm
              input={input}
              busy={busy}
              onChange={setInput}
              onSubmit={handleSubmit}
            />

            <CacheList
              names={names}
              loading={cacheLoading || loadingCached}
              error={cacheError}
              onSelect={loadCached}
              onRefresh={refresh}
              onDelete={deleteName}
              onDeleteAll={deleteAll}
              onBulkExport={startExport}
              bulkExport={bulkExportStatus}
              bulkExporting={bulkExporting}
            />
          </aside>

          {/* RIGHT — result */}
          <section>
            {showBatch ? (
              <BatchPanel
                batch={batch!}
                busy={batchBusy}
                onRetry={retryFailed}
                onClose={clearBatch}
              />
            ) : profiles.length === 0 ? (
              <div className="flex h-full min-h-[400px] flex-col items-center justify-center rounded-3xl border border-dashed border-ink/15 bg-white/40 text-center">
                <div className="text-4xl mb-4">🕯️</div>
                <p className="text-base font-medium text-ink/40">Профиль появится здесь</p>
                <p className="mt-1 text-sm text-ink/30">Введите имя и нажмите «Создать»</p>
              </div>
            ) : (
              <ProfileCard
                profile={profiles[0]}
                onRegenerate={regenerate}
                onExport={exportProfile}
                onUpload={uploadPhoto}
                onSelectPhoto={selectPhoto}
              />
            )}
          </section>

        </div>
      </main>
    </div>
  );
}
