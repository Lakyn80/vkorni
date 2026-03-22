"use client";

import { useCallback, useState } from "react";
import { api } from "@/lib/api";
import type { Profile } from "@/types";

function makeId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function loadingProfile(name: string): Profile {
  return { id: makeId(), name, text: "", photos: [], loading: true, exportState: "idle" };
}

export function useProfiles(onNameResolved: (name: string) => void) {
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [busy, setBusy] = useState(false);
  const [loadingCached, setLoadingCached] = useState(false);

  const updateProfile = useCallback((id: string, patch: Partial<Profile>) => {
    setProfiles((prev) => prev.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  }, []);

  // Generate memorial frame in background after profile loads
  const applyFrame = useCallback(
    async (profileId: string, photo: string, birth: string | null, death: string | null) => {
      if (!photo) return;
      try {
        const result = await api.frame(photo, birth, death);
        if (result.url) {
          updateProfile(profileId, { framedPhotoUrl: result.url });
        }
      } catch {
        // Frame generation is best-effort — silently ignore errors
      }
    },
    [updateProfile]
  );

  const generate = useCallback(
    async (name: string, force = false) => {
      if (!name.trim()) return;
      setBusy(true);
      const draft = loadingProfile(name);
      setProfiles([draft]);

      try {
        const data = await api.generate(name, force);
        const photos = Array.isArray(data.photos) ? data.photos : [];
        const profile: Profile = {
          id: draft.id,
          name: data.name || name,
          text: data.text || "",
          photos,
          photoSources: data.photo_sources ?? {},
          selectedPhoto: photos[0] || "",
          birth: data.birth ?? null,
          death: data.death ?? null,
          loading: false,
          error: "",
          exportState: "idle",
          framedPhotoUrl: null,
        };
        setProfiles([profile]);
        onNameResolved(data.name || name);
        // Generate frame in background
        if (photos[0]) applyFrame(draft.id, photos[0], data.birth ?? null, data.death ?? null);
      } catch (err) {
        setProfiles([
          {
            ...draft,
            loading: false,
            error: err instanceof Error ? err.message : "Ошибка генерации",
          },
        ]);
      } finally {
        setBusy(false);
      }
    },
    [onNameResolved, applyFrame]
  );

  const loadCached = useCallback(async (name: string) => {
    if (!name) return;
    setLoadingCached(true);
    const draft = loadingProfile(name);
    setProfiles([draft]);

    try {
      const data = await api.getCachedProfile(name);
      const photos = Array.isArray(data.photos) ? data.photos : [];
      const profile: Profile = {
        id: draft.id,
        name: data.name || name,
        text: data.text || "",
        photos,
        photoSources: data.photo_sources ?? {},
        selectedPhoto: photos[0] || "",
        birth: data.birth ?? null,
        death: data.death ?? null,
        loading: false,
        error: "",
        exportState: "idle",
        framedPhotoUrl: null,
      };
      setProfiles([profile]);
      // Generate frame in background
      if (photos[0]) applyFrame(draft.id, photos[0], data.birth ?? null, data.death ?? null);
    } catch (err) {
      setProfiles([
        {
          ...draft,
          loading: false,
          error: err instanceof Error ? err.message : "Ошибка загрузки профиля",
        },
      ]);
    } finally {
      setLoadingCached(false);
    }
  }, [applyFrame]);

  const regenerate = useCallback(
    async (profile: Profile) => {
      try {
        await api.deleteCache(profile.name);
        const data = await api.generate(profile.name, true);
        const photos = Array.isArray(data.photos) ? data.photos : [];
        updateProfile(profile.id, {
          text: data.text || "",
          photos,
          selectedPhoto: photos[0] || profile.selectedPhoto || "",
          error: "",
        });
      } catch (err) {
        updateProfile(profile.id, {
          error: err instanceof Error ? err.message : "Ошибка обновления",
        });
      }
    },
    [updateProfile]
  );

  const exportProfile = useCallback(
    async (profile: Profile) => {
      updateProfile(profile.id, { exportState: "sending", exportMessage: "" });
      try {
        const result = await api.export(profile);
        if (result.status === "OK") {
          const msg = result.url ? `Опубликовано: ${result.url}` : "Успешно отправлено";
          updateProfile(profile.id, { exportState: "ok", exportMessage: msg });
        } else {
          updateProfile(profile.id, {
            exportState: "error",
            exportMessage: result.error || "Ошибка экспорта",
          });
        }
      } catch (err) {
        updateProfile(profile.id, {
          exportState: "error",
          exportMessage: err instanceof Error ? err.message : "Ошибка экспорта",
        });
      }
    },
    [updateProfile]
  );

  const uploadPhoto = useCallback(
    async (profile: Profile, file: File) => {
      try {
        const result = await api.uploadPhoto(profile.name, file);
        if (result.url) {
          updateProfile(profile.id, {
            photos: [result.url, ...profile.photos],
            selectedPhoto: result.url,
          });
        }
      } catch (err) {
        updateProfile(profile.id, {
          error: err instanceof Error ? err.message : "Ошибка загрузки фото",
        });
      }
    },
    [updateProfile]
  );

  const selectPhoto = useCallback(
    (profileId: string, photo: string) => {
      updateProfile(profileId, { selectedPhoto: photo });
    },
    [updateProfile]
  );

  return {
    profiles,
    busy,
    loadingCached,
    generate,
    loadCached,
    regenerate,
    exportProfile,
    uploadPhoto,
    selectPhoto,
  };
}
