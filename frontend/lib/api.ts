import type { Profile } from "@/types";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8020";

function isAbsoluteUrl(value: string | null | undefined): value is string {
  return !!value && /^https?:\/\//i.test(value);
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `HTTP ${res.status}`);
  }
  return res.json();
}

export const api = {
  generate(name: string, force: boolean) {
    const params = new URLSearchParams({ name });
    if (force) params.set("FORCE_REGENERATE", "true");
    return request<{ name: string; text: string; photos: string[]; birth?: string | null; death?: string | null; photo_sources?: Record<string, string> }>(
      `${API_BASE}/api/generate?${params}`,
      { method: "POST" }
    );
  },

  getCacheList() {
    return request<{ names: string[] }>(`${API_BASE}/api/cache`);
  },

  getCachedProfile(name: string) {
    return request<{ name: string; text: string; photos: string[]; birth?: string | null; death?: string | null; photo_sources?: Record<string, string> }>(
      `${API_BASE}/api/cache/${encodeURIComponent(name)}`
    );
  },

  deleteCache(name: string) {
    return request<unknown>(
      `${API_BASE}/api/cache/${encodeURIComponent(name)}`,
      { method: "DELETE" }
    );
  },

  deleteAllCache() {
    return request<{ deleted: number }>(
      `${API_BASE}/api/cache`,
      { method: "DELETE" }
    );
  },

  frame(photoUrl: string, birth: string | null, death: string | null) {
    return request<{ url: string }>(
      `${API_BASE}/api/frame`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ photo_url: photoUrl, birth, death }),
      }
    );
  },

  export(profile: Pick<Profile, "name" | "text" | "photos" | "photoSources" | "selectedPhoto" | "birth" | "death" | "framedPhotoUrl">) {
    const framedPhoto = profile.framedPhotoUrl || null;
    const photo = profile.selectedPhoto || profile.photos[0] || null;
    const mappedPhotoSource = photo && profile.photoSources ? (profile.photoSources[photo] ?? null) : null;
    const directPhotoSource = isAbsoluteUrl(photo) ? photo : null;
    // Always pass the original source as backup. Backend prefers the local framed file,
    // but can re-download the source if an older cached local file is missing.
    const photoSourceUrl = mappedPhotoSource ?? directPhotoSource;
    return request<{ status: string; error?: string; url?: string }>(
      `${API_BASE}/api/export`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: profile.name,
          text: profile.text,
          photos: framedPhoto ? [framedPhoto] : (photo ? [photo] : []),
          birth: profile.birth ?? null,
          death: profile.death ?? null,
          photo_source_url: photoSourceUrl,
        }),
      }
    );
  },

  createBatch(names: string[], styleName?: string) {
    return request<{ batch_id: string; total: number; status: string }>(
      `${API_BASE}/api/batch`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names, style_name: styleName ?? null }),
      }
    );
  },

  getBatch(batchId: string) {
    return request<import("@/types").BatchStatus>(`${API_BASE}/api/batch/${batchId}`);
  },

  retryBatch(batchId: string) {
    return request<{ batch_id: string; retried: number }>(
      `${API_BASE}/api/batch/${batchId}/retry`,
      { method: "POST" }
    );
  },

  uploadPhoto(name: string, file: File) {
    const form = new FormData();
    form.append("file", file);
    return request<{ url: string }>(
      `${API_BASE}/api/upload?name=${encodeURIComponent(name)}`,
      { method: "POST", body: form }
    );
  },

  // ── Admin ─────────────────────────────────────────────────────────────────

  bulkExport(names: string[]) {
    return request<{ export_id: string; total: number }>(
      `${API_BASE}/api/bulk-export`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ names }),
      }
    );
  },

  getBulkExport(exportId: string) {
    return request<import("@/types").BulkExportStatus>(`${API_BASE}/api/bulk-export/${exportId}`);
  },

  adminLogin(username: string, password: string) {
    return request<{ access_token: string; token_type: string }>(
      `${API_BASE}/api/admin/login`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ username, password }),
      }
    );
  },

  adminChangePassword(token: string, currentPassword: string, newPassword: string) {
    return request<{ status: string }>(
      `${API_BASE}/api/admin/change-password`,
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
