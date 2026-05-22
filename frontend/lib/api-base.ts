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

function getLoopbackBackendBase(): string {
  if (typeof window === "undefined") return "";
  if (!isLoopbackHost(window.location.hostname)) return "";

  return `http://${window.location.hostname}:8020`;
}

export function getConfiguredApiBase(): string {
  const envValue = process.env.NEXT_PUBLIC_API_BASE?.trim();
  if (!envValue) return "";

  const normalized = trimTrailingSlash(envValue);
  if (typeof window === "undefined") return normalized;
  if (!isLoopbackUrl(normalized)) return normalized;

  return isLoopbackHost(window.location.hostname) ? normalized : "";
}

export function getAppUrlCandidates(path: string): string[] {
  if (!path) return [path];
  if (/^https?:\/\//i.test(path)) return [path];

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const configuredBase = getConfiguredApiBase();
  const loopbackBase = getLoopbackBackendBase();
  const candidates = [
    configuredBase || loopbackBase,
    normalizedPath,
    loopbackBase,
  ]
    .filter(Boolean)
    .map((base) => (base.startsWith("/") ? base : `${base}${normalizedPath}`));

  return [...new Set(candidates)];
}

export function toAppUrl(path: string): string {
  return getAppUrlCandidates(path)[0] ?? path;
}
