import { api } from "@/api";
import { clearAccessToken, getAccessToken, setAccessToken } from "@/auth";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  // Signed in with a now-stale access token; the refresh token lives in the (mocked-away)
  // HttpOnly cookie, so there is nothing to seed for it here.
  setAccessToken("stale-access");
});

afterEach(() => {
  clearAccessToken();
  vi.restoreAllMocks();
});

describe("token refresh", () => {
  it("spends the refresh cookie once for concurrent 401s", async () => {
    const calls: string[] = [];

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input, init) => {
      const url = String(input);
      calls.push(url);

      if (url.endsWith("/auth/refresh")) {
        // The refresh token rides in the cookie: the request carries no body, and
        // credentials must be included so the browser attaches it.
        expect(init?.body).toBeUndefined();
        expect(init?.credentials).toBe("include");
        // Single-use server-side: only the first presentation succeeds.
        const used = calls.filter((c) => c.endsWith("/auth/refresh")).length > 1;
        if (used) return jsonResponse({ detail: "unknown refresh token" }, 401);
        // Access-only response body — no refresh token.
        return jsonResponse({
          access_token: "fresh-access",
          token_type: "bearer",
          expires_in: 900,
        });
      }

      const auth = new Headers(init?.headers).get("Authorization");
      if (auth !== "Bearer fresh-access") return jsonResponse({ detail: "expired" }, 401);
      return jsonResponse(url.endsWith("/auth/me") ? { github_id: "u", login: "u" } : []);
    });

    // Exactly the mount pattern in Home: two independent requests, both holding a
    // stale access token.
    const [me, pastes] = await Promise.all([api.me(), api.listPastes()]);

    expect(calls.filter((c) => c.endsWith("/auth/refresh"))).toHaveLength(1);
    expect(me).toEqual({ github_id: "u", login: "u" });
    expect(pastes).toEqual([]);
    expect(getAccessToken()).toBe("fresh-access");
  });
});
