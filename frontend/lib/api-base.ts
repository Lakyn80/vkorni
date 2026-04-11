function trimTrailingSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

function isLoopbackHost(hostname: string): boolean {
  return hostname === "localhost" || hostname === "127.0.0.1" || hostname === "::1" || hostname === "[::1]";
}

function isLoopbackUrl(value: string): boolean {
  try {
    return isLoopbackHost(new URL(value).hostname);
  } catch {
    return false;
  }
}

export function getConfiguredApiBase(): string {
  const envValue = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (!envValue) return "";

  const normalized = trimTrailingSlash(envValue);
  if (typeof window === "undefined") return normalized;
  if (!isLoopbackUrl(normalized)) return normalized;

  return isLoopbackHost(window.location.hostname) ? normalized : "";
}

export function toAppUrl(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//i.test(path)) return path;

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const base = getConfiguredApiBase();
  return base ? `${base}${normalizedPath}` : normalizedPath;
}
