// Token storage for the web client.
//
// NOTE: for the MVP both tokens live in localStorage. Production hardening (per spec.md)
// moves the refresh token to an HttpOnly, Secure cookie set by the backend — that needs a
// backend change (the callback currently returns the pair as JSON), tracked for later.
import type { TokenPair } from "@/types";

const ACCESS_KEY = "pastry.access";
const REFRESH_KEY = "pastry.refresh";

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY);
}

export function setTokens(pair: TokenPair): void {
  localStorage.setItem(ACCESS_KEY, pair.access_token);
  localStorage.setItem(REFRESH_KEY, pair.refresh_token);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_KEY);
  localStorage.removeItem(REFRESH_KEY);
}
