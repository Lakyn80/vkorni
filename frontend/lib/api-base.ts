function trimTrailingSlash(value: string): string {
  return value.endsWith("/") ? value.slice(0, -1) : value;
}

export function getConfiguredApiBase(): string {
  const envValue = process.env.NEXT_PUBLIC_API_BASE?.trim();
  return envValue ? trimTrailingSlash(envValue) : "";
}

export function toAppUrl(path: string): string {
  if (!path) return path;
  if (/^https?:\/\//i.test(path)) return path;

  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const base = getConfiguredApiBase();
  return base ? `${base}${normalizedPath}` : normalizedPath;
}
