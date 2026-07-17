// API client. Attaches the access token, transparently refreshes once on a 401, and
// surfaces failures as ApiError. Public reads (/p/<slug>) work without a token.
import { clearTokens, getAccessToken, getRefreshToken, setTokens } from "@/auth";
import type { Me, Paste, TokenPair } from "@/types";

const API_URL = import.meta.env.VITE_API_URL ?? "";
const STATE_KEY = "pastry.oauth_state";

export class ApiError extends Error {
  status?: number;
  constructor(message: string, status?: number) {
    super(message);
    this.status = status;
  }
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

async function tryRefresh(): Promise<boolean> {
  const refresh = getRefreshToken();
  if (!refresh) return false;
  const resp = await fetch(`${API_URL}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: refresh }),
  });
  if (!resp.ok) return false;
  setTokens((await resp.json()) as TokenPair);
  return true;
}

async function request(path: string, init: RequestInit = {}, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getAccessToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");

  const resp = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (resp.status === 401 && retry && getRefreshToken()) {
    if (await tryRefresh()) return request(path, init, false);
    clearTokens();
  }
  return resp;
}

async function unwrap<T>(resp: Response): Promise<T> {
  if (!resp.ok) throw new ApiError(await errorMessage(resp), resp.status);
  return (await resp.json()) as T;
}

export const api = {
  me: () => request("/auth/me").then((r) => unwrap<Me>(r)),

  listPastes: () => request("/pastes").then((r) => unwrap<Paste[]>(r)),

  createPaste: (content: string, expiresIn?: string) =>
    request("/pastes", {
      method: "POST",
      body: JSON.stringify({ content, expires_in: expiresIn || null }),
    }).then((r) => unwrap<Paste>(r)),

  getPaste: (slug: string) => request(`/p/${slug}`).then((r) => unwrap<Paste>(r)),

  updatePaste: (slug: string, content: string) =>
    request(`/p/${slug}`, { method: "PATCH", body: JSON.stringify({ content }) }).then((r) =>
      unwrap<Paste>(r),
    ),

  deletePaste: async (slug: string): Promise<void> => {
    const resp = await request(`/p/${slug}`, { method: "DELETE" });
    if (!resp.ok && resp.status !== 204) throw new ApiError(await errorMessage(resp), resp.status);
  },
};

// --- OAuth (GitHub authorization-code flow) ---

export async function beginLogin(): Promise<void> {
  const resp = await fetch(`${API_URL}/auth/github/login`);
  const { authorize_url, state } = (await resp.json()) as { authorize_url: string; state: string };
  sessionStorage.setItem(STATE_KEY, state);
  window.location.assign(authorize_url);
}

export async function completeLogin(code: string, state: string): Promise<void> {
  const expected = sessionStorage.getItem(STATE_KEY);
  if (expected && state !== expected) throw new ApiError("OAuth state mismatch");
  const resp = await fetch(
    `${API_URL}/auth/github/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
  );
  if (!resp.ok) throw new ApiError(await errorMessage(resp), resp.status);
  setTokens((await resp.json()) as TokenPair);
  sessionStorage.removeItem(STATE_KEY);
}

export async function logout(): Promise<void> {
  const refresh = getRefreshToken();
  if (refresh) {
    try {
      await fetch(`${API_URL}/auth/logout`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refresh }),
      });
    } catch {
      /* best effort — always clear locally */
    }
  }
  clearTokens();
}
