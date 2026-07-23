// API client. Attaches the in-memory access token, transparently refreshes once on a 401
// using the HttpOnly refresh cookie, and surfaces failures as ApiError. Public reads
// (/pastes/<slug>) work without a token. Every request sends credentials so the same-origin
// refresh cookie rides along.

import { clearAccessToken, getAccessToken, markAuthResolved, setAccessToken } from "@/auth";
import type { AccessTokenResponse, Me, Paste } from "@/types";

// Same-origin under /api (CloudFront routes /api/* to the API in prod; the vite dev server
// proxies it). Kept overridable via VITE_API_URL for non-standard setups.
const API_URL = import.meta.env.VITE_API_URL ?? "/api";
const STATE_KEY = "pastry.oauth_state";

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
}

/** Message to show the user. ApiError is already user-facing; anything else is not. */
export function errorText(err: unknown): string {
  return err instanceof ApiError ? err.message : "Something went wrong.";
}

async function errorMessage(resp: Response): Promise<string> {
  if (resp.status === 404) return "paste not found";
  try {
    const body = await resp.json();
    if (typeof body.detail === "string") return body.detail;
  } catch {
    /* not JSON */
  }
  return `request failed (${resp.status})`;
}

async function doRefresh(): Promise<boolean> {
  // The refresh token rides in the HttpOnly cookie (credentials: "include"); nothing is sent
  // in the body. On success the backend returns a fresh access token and re-sets the rotated
  // cookie. A 401 means no/expired/spent cookie — i.e. not signed in.
  const resp = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    credentials: "include",
  });
  if (!resp.ok) return false;
  const data = (await resp.json()) as AccessTokenResponse;
  setAccessToken(data.access_token);
  return true;
}

// Refresh tokens are single-use server-side (auth_service.rotate_refresh deletes the row),
// so parallel 401s must not each spend one — the loser would get "unknown refresh token"
// and clear the session. Callers share whichever refresh is already in flight.
let refreshing: Promise<boolean> | null = null;

function tryRefresh(): Promise<boolean> {
  refreshing ??= doRefresh().finally(() => {
    refreshing = null;
  });
  return refreshing;
}

// Run once on app load: the access token is memory-only and gone after a reload, but the
// refresh cookie survives, so mint a new access token from it before the UI resolves. Guarded
// so React StrictMode's double-mount (and any remount) can't spend a second rotation.
let bootstrapped = false;

export async function bootstrapAuth(): Promise<void> {
  if (bootstrapped) return;
  bootstrapped = true;
  try {
    await tryRefresh();
  } finally {
    markAuthResolved();
  }
}

async function request(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${API_URL}${path}`, { ...init, headers, credentials: "include" });
  if (resp.status === 401 && retry) {
    if (await tryRefresh()) return request(path, init, false);
    clearAccessToken();
  }
  return resp;
}

async function unwrap<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw new ApiError(await errorMessage(resp), resp.status);
  return (await resp.json()) as T;
}

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  return unwrap<T>(await request(path, init));
}

export const api = {
  me: () => json<Me>("/auth/me"),

  listPastes: () => json<Paste[]>("/pastes"),

  createPaste: (content: string, expiresIn?: string) =>
    json<Paste>("/pastes", {
      method: "POST",
      body: JSON.stringify({ content, expires_in: expiresIn || null }),
    }),

  getPaste: (slug: string) => json<Paste>(`/pastes/${slug}`),

  updatePaste: (slug: string, content: string) =>
    json<Paste>(`/pastes/${slug}`, { method: "PATCH", body: JSON.stringify({ content }) }),

  deletePaste: async (slug: string): Promise<void> => {
    const resp = await request(`/pastes/${slug}`, { method: "DELETE" });
    if (!resp.ok && resp.status !== 204) throw new ApiError(await errorMessage(resp), resp.status);
  },
};

// --- OAuth (GitHub authorization-code flow) ---

export async function beginLogin(): Promise<void> {
  const resp = await fetch(`${API_URL}/auth/github/login`);
  if (!resp.ok) throw new ApiError(await errorMessage(resp), resp.status);
  const { authorize_url, state } = (await resp.json()) as { authorize_url: string; state: string };
  sessionStorage.setItem(STATE_KEY, state);
  window.location.assign(authorize_url);
}

export async function completeLogin(code: string, state: string): Promise<void> {
  // Fail closed: a missing stored state is exactly the forged-callback case, since an
  // attacker-supplied callback URL is opened in a context where beginLogin never ran.
  const expected = sessionStorage.getItem(STATE_KEY);
  if (!expected || state !== expected) throw new ApiError("OAuth state mismatch");
  const resp = await fetch(
    `${API_URL}/auth/github/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
    { credentials: "include" }, // receive the Set-Cookie refresh token
  );
  if (!resp.ok) throw new ApiError(await errorMessage(resp), resp.status);
  const data = (await resp.json()) as AccessTokenResponse;
  setAccessToken(data.access_token);
  sessionStorage.removeItem(STATE_KEY);
}

export async function logout(): Promise<void> {
  try {
    // The refresh cookie carries the token to revoke; the server also clears the cookie.
    await fetch(`${API_URL}/auth/logout`, { method: "POST", credentials: "include" });
  } catch {
    /* best effort — always clear locally */
  }
  clearAccessToken();
}
