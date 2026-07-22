import { api, ApiError, beginLogin, errorText, logout } from "@/api";
import { useAuthResolved, useSignedIn } from "@/auth";
import type { Expiry, Me, Paste } from "@/types";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";

export function Home(): JSX.Element {
  const [me, setMe] = useState<Me | null>(null);
  const [pastes, setPastes] = useState<Paste[]>([]);
  const [needsAuth, setNeedsAuth] = useState(false);
  const [content, setContent] = useState("");
  const [expiry, setExpiry] = useState<Expiry>("");
  const [editingSlug, setEditingSlug] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copiedSlug, setCopiedSlug] = useState<string | null>(null);

  // `active` lets the mount effect drop a late response after unmount; event-handler
  // callers are always mounted and can rely on the default.
  const refresh = useCallback(async (active: () => boolean = () => true) => {
    try {
      const list = await api.listPastes();
      if (!active()) return;
      setPastes(list);
      setNeedsAuth(false);
      setError(null);
    } catch (err) {
      if (!active()) return;
      if (err instanceof ApiError && err.status === 401) setNeedsAuth(true);
      else setError(errorText(err));
    }
  }, []);

  useEffect(() => {
    let active = true;

    async function load(): Promise<void> {
      // Both requests are started before either is awaited, so they overlap rather
      // than forming a waterfall.
      const mePromise = api.me();
      const pastesPromise = refresh(() => active);

      try {
        const loaded = await mePromise;
        if (active) setMe(loaded);
      } catch {
        if (active) setMe(null); // signed out is not an error worth surfacing
      }

      await pastesPromise;
    }

    void load();
    return () => {
      active = false;
    };
  }, [refresh]);

  const resetEditor = () => {
    setContent("");
    setExpiry("");
    setEditingSlug(null);
  };

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!content.trim()) return;
    setBusy(true);
    setError(null);
    try {
      if (editingSlug) await api.updatePaste(editingSlug, content);
      else await api.createPaste(content, expiry);
      resetEditor();
      await refresh();
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (paste: Paste) => {
    setEditingSlug(paste.slug);
    setContent(paste.content);
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    window.scrollTo({ top: 0, behavior: reduceMotion ? "auto" : "smooth" });
  };

  const remove = async (slug: string) => {
    if (!window.confirm(`Delete ${slug}?`)) return;
    try {
      await api.deletePaste(slug);
      if (editingSlug === slug) resetEditor();
      await refresh();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const copyLink = async (slug: string) => {
    try {
      // Throws on insecure origins, where `clipboard` is undefined entirely.
      await navigator.clipboard.writeText(`${window.location.origin}/p/${slug}`);
      setCopiedSlug(slug);
    } catch {
      setError("Could not copy to the clipboard.");
    }
  };

  const signIn = async () => {
    try {
      await beginLogin();
    } catch (err) {
      setError(errorText(err));
    }
  };

  const signOut = async () => {
    await logout();
    setMe(null);
    setPastes([]);
    setNeedsAuth(true);
    setError(null);
    resetEditor();
  };

  useEffect(() => {
    if (copiedSlug === null) return;
    const timer = window.setTimeout(() => setCopiedSlug(null), 2000);
    return () => window.clearTimeout(timer);
  }, [copiedSlug]);

  const signedIn = useSignedIn();
  const authResolved = useAuthResolved();

  return (
    <main className="container">
      <header className="topbar">
        <h1>
          <Link to="/">Pastry</Link>
        </h1>
        {/* Until the initial silent refresh resolves, render nothing rather than flashing
            the sign-in button at an already-signed-in user. */}
        {signedIn ? (
          <div className="auth">
            <span className="muted">{me ? `@${me.login}` : "signed in"}</span>
            <button type="button" className="link" onClick={() => void signOut()}>
              sign out
            </button>
          </div>
        ) : authResolved ? (
          <button type="button" className="btn" onClick={() => void signIn()}>
            Sign in with GitHub
          </button>
        ) : null}
      </header>

      <form className="editor" onSubmit={submit}>
        <label className="sr-only" htmlFor="paste-content">
          Paste content
        </label>
        <textarea
          id="paste-content"
          name="content"
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={editingSlug ? `Editing ${editingSlug}…` : "Paste your text here…"}
          rows={8}
          spellCheck={false}
        />
        <div className="editor-actions">
          {!editingSlug && (
            <label>
              Expires
              <select value={expiry} onChange={(e) => setExpiry(e.target.value as Expiry)}>
                <option value="">never</option>
                <option value="1h">1 hour</option>
                <option value="1d">1 day</option>
                <option value="1w">1 week</option>
              </select>
            </label>
          )}
          <div className="spacer" />
          {editingSlug && (
            <button type="button" className="link" onClick={resetEditor}>
              cancel
            </button>
          )}
          <button type="submit" className="btn" disabled={!signedIn || busy || !content.trim()}>
            {busy ? "Saving…" : editingSlug ? "Save changes" : "Create paste"}
          </button>
        </div>
      </form>

      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}

      {/* Announces clipboard success, which is otherwise only a button-label change. */}
      <p className="sr-only" role="status" aria-live="polite">
        {copiedSlug ? `Link to ${copiedSlug} copied to the clipboard.` : ""}
      </p>

      <section>
        <h2>Your pastes</h2>
        {needsAuth ? (
          <p className="muted">
            <button type="button" className="link" onClick={() => void signIn()}>
              Sign in
            </button>{" "}
            to see your pastes.
          </p>
        ) : pastes.length === 0 ? (
          <p className="muted">No pastes yet.</p>
        ) : (
          <ul className="pastes">
            {pastes.map((p) => (
              <li key={p.slug}>
                <Link className="slug" to={`/p/${p.slug}`}>
                  {p.slug}
                </Link>
                <span className="preview">{p.content.split("\n")[0].slice(0, 60) || "—"}</span>
                {p.expires_at && <span className="badge">expires</span>}
                <span className="row-actions">
                  <button
                    type="button"
                    className="link"
                    onClick={() => void copyLink(p.slug)}
                    aria-label={`Copy link to paste ${p.slug}`}
                  >
                    {copiedSlug === p.slug ? "copied!" : "copy link"}
                  </button>
                  <button
                    type="button"
                    className="link"
                    onClick={() => startEdit(p)}
                    aria-label={`Edit paste ${p.slug}`}
                  >
                    edit
                  </button>
                  <button
                    type="button"
                    className="link danger"
                    onClick={() => void remove(p.slug)}
                    aria-label={`Delete paste ${p.slug}`}
                  >
                    delete
                  </button>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  );
}
