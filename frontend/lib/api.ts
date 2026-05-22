import type { Profile } from "@/types";
import { getAppUrlCandidates } from "@/lib/api-base";

function isAbsoluteUrl(value: string | null | undefined): value is string {
  return !!value && /^https?:\/\//i.test(value);
}

function getErrorMessage(text: string, status: number): string {
  if (!text) return `HTTP ${status}`;

  try {
    const payload = JSON.parse(text) as { detail?: unknown; error?: unknown; message?: unknown };
    for (const value of [payload.detail, payload.error, payload.message]) {
      if (typeof value === "string" && value.trim()) {
        return value.trim();
      }
    }
  } catch {
    // Non-JSON error body.
  }

  return text;
}

function isRetryableStatus(status: number): boolean {
  return status >= 500;
}

function isRetryableNetworkError(error: unknown): boolean {
  if (!(error instanceof Error)) return false;
  return error.name === "TypeError" || /network|fetch|socket|failed/i.test(error.message);
}

export async function requestJson<T>(path: string, options?: RequestInit): Promise<T> {
  const urls = getAppUrlCandidates(path);
  let lastError: Error | null = null;

  for (let index = 0; index < urls.length; index += 1) {
    const url = urls[index];
    try {
      const res = await fetch(url, options);
      if (!res.ok) {
        const text = await res.text();
        const error = new Error(getErrorMessage(text, res.status));
        if (index < urls.length - 1 && isRetryableStatus(res.status)) {
          lastError = error;
          continue;
        }
        throw error;
      }
      return res.json();
    } catch (error) {
      if (index < urls.length - 1 && isRetryableNetworkError(error)) {
        lastError = error instanceof Error ? error : new Error(String(error));
        continue;
      }
      throw error;
    }
  }

  throw lastError ?? new Error("Request failed");
}

export const api = {
  generate(name: string, force: boolean) {
    const params = new URLSearchParams({ name });
    if (force) params.set("FORCE_REGENERATE", "true");
    return requestJson<{ name: string; text: string; photos: string[]; birth?: string | null; death?: string | null; photo_sources?: Record<string, string> }>(
      `/api/generate?${params}`,
      { method: "POST" }
    );
  },

  getCacheList() {
    return requestJson<{ names: string[] }>("/api/cache");
  },

  getCachedProfile(name: string) {
    return requestJson<{ name: string; text: string; photos: string[]; birth?: string | null; death?: string | null; photo_sources?: Record<string, string> }>(
      `/api/cache/${encodeURIComponent(name)}`
    );
  },

  deleteCache(name: string) {
    return requestJson<unknown>(
      `/api/cache/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    );
  },

  deleteAllCache() {
    return requestJson<{ deleted: number }>(
      "/api/cache",
      { method: "DELETE" }
    );
  },

  frame(photoUrl: string, birth: string | null, death: string | null, frameId?: number | null) {
    return requestJson<{ url: string; frame_id: number }>(
      "/api/frame",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_url: photoUrl, birth, death, frame_id: frameId ?? null }),
      }
    );
  },

  export(profile: Pick<Profile, "name" | "text" | "photos" | "photoSources" | "selectedPhoto" | "birth" | "death" | "framedPhotoUrl" | "framedSourcePhoto" | "frameId">) {
    const photo = profile.selectedPhoto || profile.photos[0] || null;
    const mappedPhotoSource = photo && profile.photoSources ? (profile.photoSources[photo] ?? null) : null;
    const directPhotoSource = isAbsoluteUrl(photo) ? photo : null;
    const framedPhoto =
      profile.framedPhotoUrl && profile.framedSourcePhoto === photo
        ? profile.framedPhotoUrl
        : null;
    const photoSourceUrl = mappedPhotoSource ?? directPhotoSource;
    return requestJson<{ status: string; error?: string; url?: string }>(
      "/api/export",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: profile.name,
          text: profile.text,
          photos: profile.photos,
          birth: profile.birth ?? null,
          death: profile.death ?? null,
          photo_source_url: photoSourceUrl,
          selected_photo: photo,
          photo_sources: profile.photoSources ?? {},
          framed_photo_url: framedPhoto,
          framed_source_photo: profile.framedSourcePhoto ?? null,
          frame_id: profile.frameId ?? null,
        }),
      }
    );
  },

  createBatch(names: string[], styleName?: string) {
    return requestJson<{ batch_id: string; total: number; status: string }>(
      "/api/batch",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names, style_name: styleName ?? null }),
      }
    );
  },

  getBatch(batchId: string) {
    return requestJson<import("@/types").BatchStatus>(`/api/batch/${batchId}`);
  },

  retryBatch(batchId: string) {
    return requestJson<{ batch_id: string; retried: number }>(
      `/api/batch/${batchId}/retry`,
      { method: "POST" }
    );
  },

  uploadPhoto(name: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    return requestJson<{ url: string }>(
      `/api/upload?name=${encodeURIComponent(name)}`,
      { method: "POST", body: form }
    );
  },

  // ── Admin ─────────────────────────────────────────────────────────────────

  bulkExport(names: string[]) {
    return requestJson<{ export_id: string; total: number }>(
      "/api/bulk-export",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names }),
      }
    );
  },

  getBulkExport(exportId: string) {
    return requestJson<import("@/types").BulkExportStatus>(`/api/bulk-export/${exportId}`);
  },

  adminLogin(username: string, password: string) {
    return requestJson<{ access_token: string; token_type: string }>(
      "/api/admin/login",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      }
    );
  },

  adminChangePassword(token: string, currentPassword: string, newPassword: string) {
    return requestJson<{ status: string }>(
      "/api/admin/change-password",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      }
    );
  },
};
