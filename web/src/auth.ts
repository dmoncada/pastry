// In-memory auth state for the web client, exposed as a subscribable store for components.
//
// The access JWT lives in a module variable — never in localStorage/sessionStorage — and the
// refresh token lives in an HttpOnly cookie the backend sets, so JS can read neither. On a
// full reload the in-memory token is gone; `bootstrapAuth` (see api.ts) silently re-mints it
// from the cookie before the UI resolves.
//
// Because the token is in-memory it is not shared across tabs; the old cross-tab `storage`
// listener would be dead here, so cross-tab logout is intentionally dropped (revisit with a
// BroadcastChannel if it's wanted).

import { useSyncExternalStore } from "react";

type AuthSnapshot = {
  token: string | null;
  // Whether the initial silent refresh has settled. Lets the UI tell "still checking" apart
  // from "definitely signed out" and avoid flashing the signed-out state on load.
  resolved: boolean;
};

// A fresh object per distinct state, so useSyncExternalStore can compare snapshots by
// identity; mutating in place would make it miss updates.
let snapshot: AuthSnapshot = { token: null, resolved: false };
const listeners = new Set<() => void>();

function emit(): void {
  for (const listener of listeners) listener();
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function update(next: Partial<AuthSnapshot>): void {
  snapshot = { ...snapshot, ...next };
  emit();
}

export function getAccessToken(): string | null {
  return snapshot.token;
}

export function setAccessToken(token: string): void {
  update({ token });
}

export function clearAccessToken(): void {
  update({ token: null });
}

// Called once after the initial silent refresh settles (success or failure).
export function markAuthResolved(): void {
  if (!snapshot.resolved) update({ resolved: true });
}

export function useSignedIn(): boolean {
  return useSyncExternalStore(subscribe, () => snapshot.token !== null);
}

export function useAuthResolved(): boolean {
  return useSyncExternalStore(subscribe, () => snapshot.resolved);
}
