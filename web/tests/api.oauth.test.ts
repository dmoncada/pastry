import { ApiError, completeLogin } from "@/api";
import { clearAccessToken, getAccessToken } from "@/auth";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const STATE_KEY = "pastry.oauth_state";

// The callback now returns an access-only body; the refresh token arrives as a Set-Cookie
// the browser (not JS) stores, so there is nothing refresh-related to assert here.
const ACCESS = {
  access_token: "access-1",
  token_type: "bearer",
  expires_in: 900,
};

function tokenResponse(): Response {
  return new Response(JSON.stringify(ACCESS), {
    status: 200,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  sessionStorage.clear();
  localStorage.clear();
  clearAccessToken();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("completeLogin state validation", () => {
  it("rejects a callback when no state was stored", async () => {
    // The forged-callback case: the attacker's URL is opened in a context where
    // beginLogin never ran, so sessionStorage is empty. Must fail closed.
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(tokenResponse());

    await expect(completeLogin("code-1", "attacker-state")).rejects.toThrow(ApiError);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(getAccessToken()).toBeNull();
  });

  it("rejects a state that does not match the stored one", async () => {
    sessionStorage.setItem(STATE_KEY, "real-state");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(tokenResponse());

    await expect(completeLogin("code-1", "attacker-state")).rejects.toThrow(/state mismatch/);
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(getAccessToken()).toBeNull();
  });

  it("stores the access token in memory and clears the state on a matching callback", async () => {
    sessionStorage.setItem(STATE_KEY, "real-state");
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(tokenResponse());

    await completeLogin("code-1", "real-state");

    // Access token held in memory only — never persisted to storage.
    expect(getAccessToken()).toBe("access-1");
    expect(localStorage.length).toBe(0);
    expect(sessionStorage.getItem(STATE_KEY)).toBeNull();
    // The callback fetch must include credentials so the Set-Cookie refresh token is stored.
    expect(fetchSpy.mock.calls[0]?.[1]).toMatchObject({ credentials: "include" });
  });

  it("does not store a token when the backend rejects the code", async () => {
    sessionStorage.setItem(STATE_KEY, "real-state");
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "bad code" }), {
        status: 400,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(completeLogin("code-1", "real-state")).rejects.toThrow(/bad code/);
    expect(getAccessToken()).toBeNull();
  });
});
