import { toAppUrl } from "@/lib/api-base";

export function normalizePhotoUrl(url: string): string {
  if (!url) return url;
  return toAppUrl(url);
}
