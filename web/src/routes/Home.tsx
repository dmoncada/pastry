import { api, ApiError, beginLogin, logout } from "@/api";
import { getAccessToken } from "@/auth";
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

  const refresh = useCallback(async () => {
    try {
      const list = await api.listPastes();
      setPastes(list);
      setNeedsAuth(false);
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) setNeedsAuth(true);
      else setError(String(err));
    }
  }, []);

  useEffect(() => {
    api
      .me()
      .then(setMe)
      .catch(() => setMe(null));
    void refresh();
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
      setError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const startEdit = (paste: Paste) => {
    setEditingSlug(paste.slug);
    setContent(paste.content);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const remove = async (slug: string) => {
    if (!window.confirm(`Delete ${slug}?`)) return;
    try {
      await api.deletePaste(slug);
      if (editingSlug === slug) resetEditor();
      await refresh();
    } catch (err) {
      setError(String(err));
    }
  };

  const copyLink = (slug: string) => {
    void navigator.clipboard?.writeText(`${window.location.origin}/p/${slug}`);
    setCopiedSlug(slug);
  };

  useEffect(() => {
    if (copiedSlug === null) return;
    const timer = window.setTimeout(() => setCopiedSlug(null), 2000);
    return () => window.clearTimeout(timer);
  }, [copiedSlug]);

  const signedIn = getAccessToken() !== null;

  return (
    <main className="container">
      <header className="topbar">
        <h1>
          <Link to="/">Pastry</Link>
        </h1>
        {signedIn ? (
          <div className="auth">
            <span className="muted">{me ? `@${me.login}` : "signed in"}</span>
            <button
              className="link"
              onClick={() => {
                void logout().then(() => window.location.reload());
              }}
            >
              sign out
            </button>
          </div>
        ) : (
          <button className="btn" onClick={() => void beginLogin()}>
            Sign in with GitHub
          </button>
        )}
      </header>

      <form className="editor" onSubmit={submit}>
        <textarea
          value={content}
          onChange={(e) => setContent(e.target.value)}
          placeholder={editingSlug ? `Editing ${editingSlug}…` : "Paste your text here…"}
          rows={8}
          aria-label="paste content"
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
            {editingSlug ? "Save changes" : "Create paste"}
          </button>
        </div>
      </form>

      {error && <p className="error">{error}</p>}

      <section>
        <h2>Your pastes</h2>
        {needsAuth ? (
          <p className="muted">
            <button className="link" onClick={() => void beginLogin()}>
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
                  <button className="link" onClick={() => copyLink(p.slug)}>
                    {copiedSlug === p.slug ? "copied!" : "copy link"}
                  </button>
                  <button className="link" onClick={() => startEdit(p)}>
                    edit
                  </button>
                  <button className="link danger" onClick={() => void remove(p.slug)}>
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
