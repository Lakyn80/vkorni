"use client";

import { normalizePhotoUrl } from "@/utils/photos";
import { splitParagraphs } from "@/utils/text";
import { HighlightedText } from "./HighlightedText";
import type { Profile } from "@/types";

type Props = {
  profile: Profile;
  onDrop: (e: React.DragEvent<HTMLDivElement>) => void;
};

export function MemorialFrame({ profile, onDrop }: Props) {
  const paragraphs = splitParagraphs(profile.text || "");

  return (
    <div className="border-t border-ink/10 pt-6">
      <p className="mb-3 text-xs font-semibold uppercase tracking-wider text-ink/40">
        Мемориальная карточка
      </p>

      <div
        className="overflow-hidden rounded-2xl"
        style={{
          background: "linear-gradient(145deg, #13131a 0%, #0d0d11 100%)",
          border: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div className="flex flex-col sm:flex-row">

          {/* Photo drop zone */}
          <div
            className="relative sm:w-64 shrink-0"
            onDragOver={(e) => e.preventDefault()}
            onDrop={onDrop}
          >
            {profile.selectedPhoto ? (
              <img
                src={normalizePhotoUrl(profile.selectedPhoto)}
                alt={profile.name}
                className="h-full w-full object-cover sm:min-h-[360px]"
              />
            ) : (
              <div className="flex min-h-[200px] sm:min-h-[360px] flex-col items-center justify-center gap-3 p-6 text-center">
                <span className="text-3xl opacity-60">🕯️</span>
                <p className="text-xs text-white/40 leading-snug">
                  Перетащите<br />фото сюда
                </p>
              </div>
            )}

            {/* Gradient overlay for text readability */}
            {profile.selectedPhoto && (
              <div
                className="absolute inset-0 sm:hidden"
                style={{ background: "linear-gradient(to top, #0d0d11 0%, transparent 50%)" }}
              />
            )}
          </div>

          {/* Text content */}
          <div className="flex flex-col justify-between gap-5 p-6 sm:p-7" style={{ color: "#f4f2ec" }}>
            {/* Header */}
            <div>
              <p className="mb-1 text-xs font-semibold uppercase tracking-[0.2em] opacity-50">
                Память
              </p>
              <h3
                className="text-2xl font-semibold leading-tight"
                style={{ fontFamily: "var(--font-display)" }}
              >
                {profile.name}
              </h3>
              {(profile.birth || profile.death) && (
                <p className="mt-1.5 text-sm" style={{ color: "#ffbd7a" }}>
                  {profile.birth ?? "??"} — {profile.death ?? "жив"}
                </p>
              )}
            </div>

            {/* Bio text */}
            {paragraphs.length > 0 && (
              <div className="flex flex-col gap-3 text-sm leading-relaxed max-h-52 overflow-y-auto pr-1" style={{ color: "rgba(244,242,236,0.8)" }}>
                {paragraphs.slice(0, 4).map((paragraph, index) => (
                  <p
                    key={`${profile.id}-${index}`}
                    className={index === 0 ? "font-semibold" : ""}
                    style={index === 0 ? { color: "rgba(244,242,236,0.95)" } : {}}
                  >
                    <HighlightedText text={paragraph} />
                  </p>
                ))}
              </div>
            )}

            {/* Footer */}
            <p className="text-xs opacity-40 border-t border-white/10 pt-4">
              Вечная память · Светлая благодарность
            </p>
          </div>
        </div>
      </div>

      {profile.photos.length > 1 && (
        <p className="mt-2 text-xs text-ink/30">
          Перетащите любое фото в карточку
        </p>
      )}
    </div>
  );
}
