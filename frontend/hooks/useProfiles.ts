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

  const applyFrame = useCallback(
    async (
      profileId: string,
      photo: string,
      birth: string | null,
      death: string | null,
      existingFrameId?: number | null
    ) => {
      if (!photo) return;
      try {
        const result = await api.frame(photo, birth, death, existingFrameId ?? null);
        if (result.url) {
          setProfiles((prev) =>
            prev.map((profile) => {
              if (profile.id !== profileId) return profile;
              if (profile.selectedPhoto !== photo) return profile;
              return {
                ...profile,
                framedPhotoUrl: result.url,
                framedPreviewVersion: Date.now(),
                framedSourcePhoto: photo,
                frameId: result.frame_id,
              };
            })
          );
        }
      } catch {
        // Frame generation is best-effort — silently ignore errors
      }
    },
    []
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
          framedSourcePhoto: null,
          frameId: null,
          birth: data.birth ?? null,
          death: data.death ?? null,
          loading: false,
          error: "",
          exportState: "idle",
          framedPhotoUrl: null,
          framedPreviewVersion: null,
        };
        setProfiles([profile]);
        onNameResolved(data.name || name);
        if (photos[0]) {
          applyFrame(draft.id, photos[0], data.birth ?? null, data.death ?? null, null);
        }
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

  const loadCached = useCallback(
    async (name: string) => {
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
          framedSourcePhoto: null,
          frameId: null,
          birth: data.birth ?? null,
          death: data.death ?? null,
          loading: false,
          error: "",
          exportState: "idle",
          framedPhotoUrl: null,
          framedPreviewVersion: null,
        };
        setProfiles([profile]);
        if (photos[0]) {
          applyFrame(draft.id, photos[0], data.birth ?? null, data.death ?? null, null);
        }
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
    },
    [applyFrame]
  );

  const regenerate = useCallback(
    async (profile: Profile) => {
      try {
        const data = await api.generate(profile.name, true);
        const photos = Array.isArray(data.photos) ? data.photos : [];
        const nextSelectedPhoto = photos[0] || profile.selectedPhoto || "";
        updateProfile(profile.id, {
          text: data.text || "",
          photos,
          photoSources: data.photo_sources ?? {},
          selectedPhoto: nextSelectedPhoto,
          framedSourcePhoto: null,
          frameId: null,
          birth: data.birth ?? null,
          death: data.death ?? null,
          framedPhotoUrl: null,
          framedPreviewVersion: null,
          error: "",
        });
        if (nextSelectedPhoto) {
          applyFrame(profile.id, nextSelectedPhoto, data.birth ?? null, data.death ?? null, null);
        }
      } catch (err) {
        updateProfile(profile.id, {
          error: err instanceof Error ? err.message : "Ошибка обновления",
        });
      }
    },
    [applyFrame, updateProfile]
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
          const nextPhotos = [result.url, ...profile.photos.filter((photo) => photo !== result.url)];
          updateProfile(profile.id, {
            photos: nextPhotos,
            selectedPhoto: result.url,
            framedPhotoUrl: null,
            framedPreviewVersion: null,
            framedSourcePhoto: null,
            frameId: null,
          });
          applyFrame(profile.id, result.url, profile.birth ?? null, profile.death ?? null, null);
        }
      } catch (err) {
        updateProfile(profile.id, {
          error: err instanceof Error ? err.message : "Ошибка загрузки фото",
        });
      }
    },
    [applyFrame, updateProfile]
  );

  const selectPhoto = useCallback(
    (profileId: string, photo: string) => {
      const currentProfile = profiles.find((profile) => profile.id === profileId);
      const nextBirth = currentProfile?.birth ?? null;
      const nextDeath = currentProfile?.death ?? null;

      setProfiles((prev) =>
        prev.map((profile) => {
          if (profile.id !== profileId) return profile;
          return {
            ...profile,
            selectedPhoto: photo,
            framedPhotoUrl: null,
            framedPreviewVersion: null,
            framedSourcePhoto: null,
            frameId: null,
          };
        })
      );

      applyFrame(profileId, photo, nextBirth, nextDeath, null);
    },
    [applyFrame, profiles]
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
