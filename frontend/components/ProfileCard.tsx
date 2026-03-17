"use client";

import { PhotoGrid } from "./PhotoGrid";
import { MemorialFrame } from "./MemorialFrame";
import type { Profile } from "@/types";

type Props = {
  profile: Profile;
  onRegenerate: (p: Profile) => void;
  onExport: (p: Profile) => void;
  onUpload: (p: Profile, file: File) => void;
  onSelectPhoto: (profileId: string, photo: string) => void;
};

export function ProfileCard({ profile, onRegenerate, onExport, onUpload, onSelectPhoto }: Props) {
  function handleDragStart(e: React.DragEvent<HTMLDivElement>, photo: string) {
    e.dataTransfer.setData("text/plain", photo);
  }

  function handleDrop(e: React.DragEvent<HTMLDivElement>) {
    e.preventDefault();
    const photo = e.dataTransfer.getData("text/plain");
    if (photo) onSelectPhoto(profile.id, photo);
  }

  return (
    <div className="flex flex-col gap-6 animate-rise">

      {/* Header */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wider text-ink/40">Профиль</p>
          <h2 className="mt-0.5 text-2xl font-semibold text-ink" style={{ fontFamily: "var(--font-display)" }}>
            {profile.name}
          </h2>
        </div>

        <div className="flex flex-wrap gap-2">
          <label className="cursor-pointer rounded-xl border border-ink/15 bg-white px-3 py-2 text-xs font-semibold text-ink/70 transition-all hover:border-ink/30 hover:text-ink">
            ↑ Фото
            <input
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) onUpload(profile, file);
                e.target.value = "";
              }}
            />
          </label>
          <button
            onClick={() => onRegenerate(profile)}
            disabled={profile.loading}
            className="rounded-xl border border-ink/15 bg-white px-3 py-2 text-xs font-semibold text-ink/70 transition-all hover:border-ink/30 hover:text-ink disabled:opacity-40"
          >
            ↺ Регенерировать
          </button>
          <button
            onClick={() => onExport(profile)}
            disabled={profile.loading || !profile.text}
            className="rounded-xl bg-ember px-4 py-2 text-xs font-semibold text-white shadow-sm transition-all hover:bg-ember/90 disabled:opacity-40"
          >
            {profile.exportState === "sending" ? "⏳ Отправка..." : "→ vkorni.com"}
          </button>
        </div>
      </div>

      {/* Export status */}
      {profile.exportState === "ok" && (
        <div className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-700">
          ✓ {profile.exportMessage || "Успешно отправлено на vkorni.com"}
        </div>
      )}
      {profile.exportState === "error" && (
        <div className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-600">
          ✕ {profile.exportMessage}
        </div>
      )}

      {/* Loading / Error / Bio text */}
      {profile.loading ? (
        <div className="flex items-center gap-3 rounded-2xl border border-ink/8 bg-white/60 p-6">
          <span className="h-5 w-5 animate-spin rounded-full border-2 border-ink/20 border-t-ink/70" />
          <span className="text-sm text-ink/60">Генерируем биографию, пожалуйста подождите...</span>
        </div>
      ) : profile.error ? (
        <div className="rounded-2xl border border-red-100 bg-red-50 p-4 text-sm text-red-600">
          {profile.error}
        </div>
      ) : profile.text ? (
        <div className="rounded-2xl border border-ink/8 bg-white/60 p-5 text-sm leading-relaxed text-ink/75 max-h-48 overflow-y-auto">
          {profile.text}
        </div>
      ) : null}

      {/* Photos */}
      <PhotoGrid
        photos={profile.photos}
        selectedPhoto={profile.selectedPhoto}
        profileName={profile.name}
        onSelect={(photo) => onSelectPhoto(profile.id, photo)}
        onDragStart={handleDragStart}
      />

      {/* Memorial frame */}
      <MemorialFrame profile={profile} onDrop={handleDrop} />
    </div>
  );
}
