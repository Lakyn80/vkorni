"use client";

import { useEffect, useMemo, useState } from "react";
import { toAppUrl } from "@/lib/api-base";
import { normalizePhotoUrl } from "@/utils/photos";

type StoredProfileListItem = {
  id: number;
  name: string;
  birth?: string | null;
  death?: string | null;
  selected_photo_url?: string | null;
  selected_source_url?: string | null;
  framed_image_url?: string | null;
  attachment_url?: string | null;
  last_thread_id?: number | null;
  last_thread_url?: string | null;
  status: string;
  created_at: number;
  updated_at: number;
  last_exported_at: number;
};

type StoredProfilePhoto = {
  id: number;
  photo_url: string;
  source_url?: string | null;
  sort_order: number;
  is_selected: boolean;
};

type StoredProfileAttempt = {
  id: number;
  status: string;
  export_kind: string;
  thread_id?: number | null;
  thread_url?: string | null;
  attachment_id?: number | null;
  attachment_url?: string | null;
  error?: string | null;
  created_at: number;
};

type StoredProfileDetail = StoredProfileListItem & {
  text?: string | null;
  frame_id?: number | null;
  attachment_id?: number | null;
  framed_image_path?: string | null;
  photos: StoredProfilePhoto[];
  export_attempts: StoredProfileAttempt[];
};

type ApiError = {
  detail?: string;
};

function formatDateTime(value?: number | null): string {
  if (!value) return "Neznámé datum";
  return new Intl.DateTimeFormat("cs-CZ", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value * 1000));
}

function formatYears(birth?: string | null, death?: string | null): string {
  if (!birth && !death) return "Roky neuvedeny";
  return `${birth || "?"} - ${death || "?"}`;
}

function summarizeError(message?: string | null): string {
  if (!message) return "Bez chyby";
  return message.length > 140 ? `${message.slice(0, 140)}…` : message;
}

function getPreviewUrl(profile: {
  framed_image_url?: string | null;
  attachment_url?: string | null;
  selected_photo_url?: string | null;
}): string | null {
  const raw = profile.framed_image_url || profile.attachment_url || profile.selected_photo_url;
  return raw ? normalizePhotoUrl(raw) : null;
}

function statusClasses(status: string): string {
  if (status === "OK") return "bg-emerald-50 text-emerald-700 border-emerald-200";
  if (status === "ERROR") return "bg-red-50 text-red-600 border-red-200";
  return "bg-amber-50 text-amber-700 border-amber-200";
}

async function readJson<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const raw = await res.text();
    let message = raw || `HTTP ${res.status}`;
    if (raw) {
      try {
        const payload = JSON.parse(raw) as ApiError;
        if (payload.detail) message = payload.detail;
      } catch {
        // keep raw text message
      }
    }
    throw new Error(message);
  }
  return res.json();
}

export default function StoredProfilesPanel() {
  const [profiles, setProfiles] = useState<StoredProfileListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<StoredProfileDetail | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<"all" | "OK" | "ERROR">("all");
  const [loadingList, setLoadingList] = useState(true);
  const [loadingDetail, setLoadingDetail] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [resending, setResending] = useState(false);
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);

  const filteredProfiles = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase("cs-CZ");
    return profiles.filter((profile) => {
      const matchesText = !needle || profile.name.toLocaleLowerCase("cs-CZ").includes(needle);
      const matchesStatus = statusFilter === "all" || profile.status === statusFilter;
      return matchesText && matchesStatus;
    });
  }, [profiles, query, statusFilter]);

  async function loadProfiles(preserveSelection = true) {
    setRefreshing(true);
    try {
      const payload = await readJson<{ profiles: StoredProfileListItem[] }>(toAppUrl("/api/exported-profiles"));
      setProfiles(payload.profiles);
      setSelectedId((current) => {
        if (preserveSelection && current && payload.profiles.some((profile) => profile.id === current)) {
          return current;
        }
        return payload.profiles[0]?.id ?? null;
      });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Nepodařilo se načíst archiv exportů" });
    } finally {
      setLoadingList(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    void loadProfiles(false);
  }, []);

  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      return;
    }

    let cancelled = false;
    setLoadingDetail(true);
    void readJson<StoredProfileDetail>(toAppUrl(`/api/exported-profiles/${selectedId}`))
      .then((payload) => {
        if (!cancelled) setDetail(payload);
      })
      .catch((err) => {
        if (!cancelled) {
          setDetail(null);
          setMessage({ ok: false, text: err instanceof Error ? err.message : "Nepodařilo se načíst detail profilu" });
        }
      })
      .finally(() => {
        if (!cancelled) setLoadingDetail(false);
      });

    return () => {
      cancelled = true;
    };
  }, [selectedId]);

  async function handleResend() {
    if (!detail) return;
    setResending(true);
    setMessage(null);
    try {
      const result = await readJson<{ status: string; error?: string; url?: string }>(
        toAppUrl(`/api/exported-profiles/${detail.id}/resend`),
        { method: "POST" }
      );
      if (result.status === "OK") {
        setMessage({ ok: true, text: result.url ? `Profil byl znovu odeslán: ${result.url}` : "Profil byl znovu odeslán" });
      } else {
        setMessage({ ok: false, text: result.error || "Resend skončil chybou" });
      }
      await loadProfiles(true);
      const refreshed = await readJson<StoredProfileDetail>(toAppUrl(`/api/exported-profiles/${detail.id}`));
      setDetail(refreshed);
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Resend se nezdařil" });
    } finally {
      setResending(false);
    }
  }

  const selectedPreview = detail ? getPreviewUrl(detail) : null;

  return (
    <section className="rounded-[28px] border border-ink/10 bg-white/75 p-5 shadow-soft backdrop-blur">
      <div className="mb-5 flex flex-col gap-4 border-b border-ink/10 pb-5 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <span className="text-[11px] font-bold uppercase tracking-[0.28em] text-lake/60">Archiv exportu</span>
          <h2 className="mt-2 text-2xl font-semibold text-ink" style={{ fontFamily: "var(--font-display)" }}>
            Uložené profily z databáze
          </h2>
          <p className="mt-2 max-w-2xl text-sm text-ink/60">
            Vlevo je filtrovací seznam exportovaných profilů, vpravo detail uložený v DB včetně pokusů o odeslání a tlačítka pro znovuodeslání.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <span className="rounded-full border border-ink/10 bg-white px-3 py-1 text-xs text-ink/55">
            {filteredProfiles.length} / {profiles.length} profilů
          </span>
          <button
            type="button"
            onClick={() => void loadProfiles(true)}
            disabled={refreshing}
            className="rounded-full border border-ink/15 bg-white px-4 py-2 text-sm font-semibold text-ink transition-colors hover:border-ink/30 hover:bg-ink/5 disabled:opacity-50"
          >
            {refreshing ? "Obnovuji…" : "Obnovit"}
          </button>
        </div>
      </div>

      <div className="mb-5 grid gap-3 md:grid-cols-[minmax(0,1fr),180px]">
        <input
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Hledat podle jména"
          className="rounded-2xl border border-ink/15 bg-white px-4 py-3 text-sm text-ink placeholder:text-ink/35 focus:outline-none focus:ring-2 focus:ring-lake/20"
        />
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value as "all" | "OK" | "ERROR")}
          className="rounded-2xl border border-ink/15 bg-white px-4 py-3 text-sm text-ink focus:outline-none focus:ring-2 focus:ring-lake/20"
        >
          <option value="all">Všechny stavy</option>
          <option value="OK">Úspěšné</option>
          <option value="ERROR">Chybové</option>
        </select>
      </div>

      {message && (
        <div className={`mb-5 rounded-2xl border px-4 py-3 text-sm ${message.ok ? "border-emerald-200 bg-emerald-50 text-emerald-700" : "border-red-200 bg-red-50 text-red-600"}`}>
          {message.text}
        </div>
      )}

      <div className="grid gap-5 xl:grid-cols-[360px,minmax(0,1fr)]">
        <div className="rounded-[24px] border border-ink/10 bg-[#f8f8f5] p-3">
          <div className="mb-3 flex items-center justify-between px-2">
            <h3 className="text-sm font-semibold text-ink">Seznam profilů</h3>
            {loadingList ? <span className="text-xs text-ink/40">Načítám…</span> : null}
          </div>
          <div className="max-h-[720px] space-y-2 overflow-y-auto pr-1">
            {!loadingList && filteredProfiles.length === 0 ? (
              <div className="rounded-2xl border border-dashed border-ink/15 bg-white px-4 py-6 text-sm text-ink/50">
                Filtru neodpovídá žádný uložený profil.
              </div>
            ) : null}

            {filteredProfiles.map((profile) => {
              const previewUrl = getPreviewUrl(profile);
              const selected = profile.id === selectedId;
              return (
                <button
                  key={profile.id}
                  type="button"
                  onClick={() => setSelectedId(profile.id)}
                  className={`flex w-full gap-3 rounded-[22px] border px-3 py-3 text-left transition-all ${
                    selected
                      ? "border-lake/35 bg-white shadow-sm"
                      : "border-transparent bg-white/65 hover:border-ink/10 hover:bg-white"
                  }`}
                >
                  <div className="h-16 w-14 shrink-0 overflow-hidden rounded-2xl bg-mist">
                    {previewUrl ? (
                      // eslint-disable-next-line @next/next/no-img-element
                      <img src={previewUrl} alt={profile.name} className="h-full w-full object-cover" />
                    ) : (
                      <div className="flex h-full w-full items-center justify-center text-[10px] uppercase tracking-[0.2em] text-ink/30">
                        Bez foto
                      </div>
                    )}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <p className="line-clamp-2 text-sm font-semibold text-ink">{profile.name}</p>
                      <span className={`shrink-0 rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${statusClasses(profile.status)}`}>
                        {profile.status}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-ink/45">{formatYears(profile.birth, profile.death)}</p>
                    <p className="mt-2 text-xs text-ink/45">Naposledy: {formatDateTime(profile.last_exported_at)}</p>
                    {profile.last_thread_url ? (
                      <p className="mt-1 truncate text-xs text-lake/70">{profile.last_thread_url}</p>
                    ) : null}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        <div className="rounded-[24px] border border-ink/10 bg-[#fcfcfa] p-4">
          {!selectedId ? (
            <div className="flex min-h-[420px] items-center justify-center rounded-[20px] border border-dashed border-ink/15 bg-white text-sm text-ink/45">
              Vyber profil vlevo.
            </div>
          ) : loadingDetail ? (
            <div className="flex min-h-[420px] items-center justify-center rounded-[20px] border border-dashed border-ink/15 bg-white text-sm text-ink/45">
              Načítám detail profilu…
            </div>
          ) : detail ? (
            <div className="space-y-5">
              <div className="flex flex-col gap-4 rounded-[22px] bg-white p-4 md:flex-row">
                <div className="h-56 w-full overflow-hidden rounded-[20px] bg-mist md:w-48 md:shrink-0">
                  {selectedPreview ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={selectedPreview} alt={detail.name} className="h-full w-full object-cover" />
                  ) : (
                    <div className="flex h-full w-full items-center justify-center text-xs uppercase tracking-[0.2em] text-ink/30">
                      Bez náhledu
                    </div>
                  )}
                </div>

                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <span className="text-[11px] font-bold uppercase tracking-[0.24em] text-lake/55">Detail profilu</span>
                      <h3 className="mt-2 text-2xl font-semibold text-ink" style={{ fontFamily: "var(--font-display)" }}>
                        {detail.name}
                      </h3>
                      <p className="mt-2 text-sm text-ink/55">{formatYears(detail.birth, detail.death)}</p>
                    </div>
                    <span className={`rounded-full border px-3 py-1 text-xs font-bold uppercase tracking-[0.18em] ${statusClasses(detail.status)}`}>
                      {detail.status}
                    </span>
                  </div>

                  <div className="mt-4 grid gap-3 sm:grid-cols-2">
                    <div className="rounded-2xl border border-ink/10 bg-[#f7f7f3] px-3 py-3 text-sm text-ink/60">
                      <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-ink/35">Poslední export</div>
                      <div className="mt-2 font-medium text-ink">{formatDateTime(detail.last_exported_at)}</div>
                    </div>
                    <div className="rounded-2xl border border-ink/10 bg-[#f7f7f3] px-3 py-3 text-sm text-ink/60">
                      <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-ink/35">Pokusů celkem</div>
                      <div className="mt-2 font-medium text-ink">{detail.export_attempts.length}</div>
                    </div>
                  </div>

                  <div className="mt-4 flex flex-wrap gap-3">
                    {detail.last_thread_url ? (
                      <a
                        href={detail.last_thread_url}
                        target="_blank"
                        rel="noreferrer"
                        className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-ink/85"
                      >
                        Otevřít thread
                      </a>
                    ) : null}
                    <button
                      type="button"
                      onClick={() => void handleResend()}
                      disabled={resending}
                      className="rounded-full border border-lake/20 bg-lake/10 px-4 py-2 text-sm font-semibold text-lake transition-colors hover:bg-lake/15 disabled:opacity-50"
                    >
                      {resending ? "Odesílám…" : "Znovu odeslat z DB"}
                    </button>
                  </div>
                </div>
              </div>

              <div className="grid gap-5 2xl:grid-cols-[minmax(0,1.3fr),minmax(320px,0.9fr)]">
                <div className="rounded-[22px] border border-ink/10 bg-white p-4">
                  <div className="mb-3 flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-ink">Uložený text</h4>
                    <span className="text-xs text-ink/35">{detail.text?.length || 0} znaků</span>
                  </div>
                  <div className="max-h-[420px] overflow-y-auto whitespace-pre-line rounded-2xl bg-[#f7f7f3] px-4 py-4 text-sm leading-7 text-ink/75">
                    {detail.text || "Text není uložen."}
                  </div>
                </div>

                <div className="space-y-5">
                  <div className="rounded-[22px] border border-ink/10 bg-white p-4">
                    <h4 className="mb-3 text-sm font-semibold text-ink">Metadata</h4>
                    <dl className="space-y-3 text-sm">
                      <div className="rounded-2xl bg-[#f7f7f3] px-3 py-3">
                        <dt className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink/35">Vybraná fotka</dt>
                        <dd className="mt-1 break-all text-ink/70">{detail.selected_photo_url || "Neuloženo"}</dd>
                      </div>
                      <div className="rounded-2xl bg-[#f7f7f3] px-3 py-3">
                        <dt className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink/35">Zdroj fotky</dt>
                        <dd className="mt-1 break-all text-ink/70">{detail.selected_source_url || "Neuloženo"}</dd>
                      </div>
                      <div className="rounded-2xl bg-[#f7f7f3] px-3 py-3">
                        <dt className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink/35">Frame ID</dt>
                        <dd className="mt-1 text-ink/70">{detail.frame_id ?? "Neurčeno"}</dd>
                      </div>
                      <div className="rounded-2xl bg-[#f7f7f3] px-3 py-3">
                        <dt className="text-[11px] font-bold uppercase tracking-[0.18em] text-ink/35">Aktuální attachment</dt>
                        <dd className="mt-1 break-all text-ink/70">{detail.attachment_url || "Neuloženo"}</dd>
                      </div>
                    </dl>
                  </div>

                  <div className="rounded-[22px] border border-ink/10 bg-white p-4">
                    <div className="mb-3 flex items-center justify-between">
                      <h4 className="text-sm font-semibold text-ink">Historie odeslání</h4>
                      <span className="text-xs text-ink/35">{detail.export_attempts.length} záznamů</span>
                    </div>
                    <div className="max-h-[360px] space-y-3 overflow-y-auto pr-1">
                      {detail.export_attempts.length === 0 ? (
                        <div className="rounded-2xl bg-[#f7f7f3] px-4 py-4 text-sm text-ink/45">
                          Historie pokusů zatím není k dispozici.
                        </div>
                      ) : null}
                      {detail.export_attempts.map((attempt) => (
                        <div key={attempt.id} className="rounded-2xl border border-ink/10 bg-[#f7f7f3] px-4 py-3">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span className={`rounded-full border px-2 py-1 text-[10px] font-bold uppercase tracking-[0.18em] ${statusClasses(attempt.status)}`}>
                                {attempt.status}
                              </span>
                              <span className="text-xs font-semibold uppercase tracking-[0.18em] text-ink/35">
                                {attempt.export_kind}
                              </span>
                            </div>
                            <span className="text-xs text-ink/45">{formatDateTime(attempt.created_at)}</span>
                          </div>
                          {attempt.thread_url ? (
                            <a href={attempt.thread_url} target="_blank" rel="noreferrer" className="mt-2 block break-all text-xs text-lake hover:text-lake/80">
                              {attempt.thread_url}
                            </a>
                          ) : null}
                          <p className="mt-2 text-sm text-ink/65">{summarizeError(attempt.error)}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <div className="flex min-h-[420px] items-center justify-center rounded-[20px] border border-dashed border-ink/15 bg-white text-sm text-ink/45">
              Detail profilu se nepodařilo načíst.
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
