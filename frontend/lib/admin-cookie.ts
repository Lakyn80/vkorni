const TOKEN_COOKIE_NAME = "vkorni_token";
const TOKEN_TTL_SECONDS = 60 * 60;

function getBaseAttributes(): string[] {
  const attributes = ["Path=/", "SameSite=Lax"];

  if (window.location.protocol === "https:") {
    attributes.push("Secure");
  }

  return attributes;
}

export function setAdminTokenCookie(token: string) {
  const expiresAt = new Date(Date.now() + TOKEN_TTL_SECONDS * 1000).toUTCString();

  document.cookie = [
    `${TOKEN_COOKIE_NAME}=${encodeURIComponent(token)}`,
    ...getBaseAttributes(),
    `Max-Age=${TOKEN_TTL_SECONDS}`,
    `Expires=${expiresAt}`,
  ].join("; ");
}

export function clearAdminTokenCookie() {
  document.cookie = [
    `${TOKEN_COOKIE_NAME}=`,
    ...getBaseAttributes(),
    "Max-Age=0",
    "Expires=Thu, 01 Jan 1970 00:00:00 GMT",
  ].join("; ");
}

export function getAdminTokenCookie(): string {
  const match = document.cookie.match(new RegExp(`(?:^|;\\s*)${TOKEN_COOKIE_NAME}=([^;]+)`));
  if (!match) return "";

  try {
    return decodeURIComponent(match[1]);
  } catch {
    return match[1];
  }
}
