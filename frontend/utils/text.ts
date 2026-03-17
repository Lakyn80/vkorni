export const HIGHLIGHT_WORDS = [
  "родился", "родилась", "умер", "умерла", "память", "наследие",
  "карьера", "альбом", "сцена", "концерт", "фильм", "книга",
  "премия", "подвиг", "служба", "семья",
];

export function splitParagraphs(text: string): string[] {
  if (!text) return [];
  const normalized = text.replace(/\r\n/g, "\n").trim();
  if (!normalized) return [];
  let parts = normalized.split(/\n\s*\n/);
  if (parts.length === 1) parts = normalized.split(/\n+/);
  return parts.map((p) => p.trim()).filter(Boolean);
}

export function extractYears(text: string): { birth: number | null; death: number | null } {
  const matches = text.match(/\b(18|19|20)\d{2}\b/g) || [];
  const years = Array.from(new Set(matches)).map(Number).sort((a, b) => a - b);
  if (years.length >= 2) return { birth: years[0], death: years[years.length - 1] };
  return { birth: null, death: null };
}

export function buildHighlightRegex(): RegExp {
  return new RegExp(`(\\b\\d{4}\\b|${HIGHLIGHT_WORDS.join("|")})`, "gi");
}
