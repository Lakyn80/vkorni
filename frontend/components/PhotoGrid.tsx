"use client";

import { normalizePhotoUrl } from "@/utils/photos";

type Props = {
  photos: string[];
  selectedPhoto?: string;
  profileName: string;
  onSelect: (photo: string) => void;
  onDragStart: (e: React.DragEvent<HTMLDivElement>, photo: string) => void;
};

export function PhotoGrid({ photos, selectedPhoto, profileName, onSelect, onDragStart }: Props) {
  if (photos.length === 0) return null;

  return (
    <div>
      <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ink/40">
        Фотографии ({photos.length})
      </p>
      <div className="grid grid-cols-4 gap-2 sm:grid-cols-6">
        {photos.map((photo) => (
          <div
            key={photo}
            draggable
            onDragStart={(e) => onDragStart(e, photo)}
            onClick={() => onSelect(photo)}
            className={`group relative cursor-pointer overflow-hidden rounded-xl border-2 transition-all ${
              selectedPhoto === photo
                ? "border-lake shadow-md shadow-lake/20"
                : "border-transparent hover:border-ink/20"
            }`}
          >
            <img
              src={normalizePhotoUrl(photo)}
              alt={profileName}
              className="aspect-square w-full object-cover"
              loading="lazy"
            />
            {selectedPhoto === photo && (
              <div className="absolute inset-0 bg-lake/10 flex items-center justify-center">
                <span className="rounded-full bg-lake text-white text-xs px-1.5 py-0.5">✓</span>
              </div>
            )}
          </div>
        ))}
      </div>
      <p className="mt-1.5 text-xs text-ink/30">Нажмите для выбора · Перетащите в рамку</p>
    </div>
  );
}
