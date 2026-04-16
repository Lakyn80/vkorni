import type { Profile } from "@/types";
import { toAppUrl } from "@/lib/api-base";

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

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(getErrorMessage(text, res.status));
  }
  return res.json();
}

export const api = {
  generate(name: string, force: boolean) {
    const params = new URLSearchParams({ name });
    if (force) params.set("FORCE_REGENERATE", "true");
    return request<{ name: string; text: string; photos: string[]; birth?: string | null; death?: string | null; photo_sources?: Record<string, string> }>(
      toAppUrl(`/api/generate?${params}`),
      { method: "POST" }
    );
  },

  getCacheList() {
    return request<{ names: string[] }>(toAppUrl("/api/cache"));
  },

  getCachedProfile(name: string) {
    return request<{ name: string; text: string; photos: string[]; birth?: string | null; death?: string | null; photo_sources?: Record<string, string> }>(
      toAppUrl(`/api/cache/${encodeURIComponent(name)}`)
    );
  },

  deleteCache(name: string) {
    return request<unknown>(
      toAppUrl(`/api/cache/${encodeURIComponent(name)}`),
      { method: "DELETE" }
    );
  },

  deleteAllCache() {
    return request<{ deleted: number }>(
      toAppUrl("/api/cache"),
      { method: "DELETE" }
    );
  },

  frame(photoUrl: string, birth: string | null, death: string | null, frameId?: number | null) {
    return request<{ url: string; frame_id: number }>(
      toAppUrl("/api/frame"),
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
    return request<{ status: string; error?: string; url?: string }>(
      toAppUrl("/api/export"),
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
    return request<{ batch_id: string; total: number; status: string }>(
      toAppUrl("/api/batch"),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names, style_name: styleName ?? null }),
      }
    );
  },

  getBatch(batchId: string) {
    return request<import("@/types").BatchStatus>(toAppUrl(`/api/batch/${batchId}`));
  },

  retryBatch(batchId: string) {
    return request<{ batch_id: string; retried: number }>(
      toAppUrl(`/api/batch/${batchId}/retry`),
      { method: "POST" }
    );
  },

  uploadPhoto(name: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    return request<{ url: string }>(
      toAppUrl(`/api/upload?name=${encodeURIComponent(name)}`),
      { method: "POST", body: form }
    );
  },

  // ── Admin ─────────────────────────────────────────────────────────────────

  bulkExport(names: string[]) {
    return request<{ export_id: string; total: number }>(
      toAppUrl("/api/bulk-export"),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names }),
      }
    );
  },

  getBulkExport(exportId: string) {
    return request<import("@/types").BulkExportStatus>(toAppUrl(`/api/bulk-export/${exportId}`));
  },

  adminLogin(username: string, password: string) {
    return request<{ access_token: string; token_type: string }>(
      toAppUrl("/api/admin/login"),
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      }
    );
  },

  adminChangePassword(token: string, currentPassword: string, newPassword: string) {
    return request<{ status: string }>(
      toAppUrl("/api/admin/change-password"),
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
