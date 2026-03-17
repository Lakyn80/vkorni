const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8020";

export function normalizePhotoUrl(url: string): string {
  if (!url) return url;
  if (url.startsWith("/")) return `${API_BASE}${url}`;
  return url;
}
