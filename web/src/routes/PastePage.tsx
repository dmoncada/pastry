import { api, ApiError } from "@/api";
import type { Paste } from "@/types";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

type Status = "loading" | "ok" | "notfound" | "error";
type CopyState = "idle" | "copied" | "failed";

const COPY_LABEL: Record<CopyState, string> = {
  idle: "copy",
  copied: "copied!",
  failed: "copy failed",
};

export function PastePage(): JSX.Element {
  const { slug = "" } = useParams();
  const [status, setStatus] = useState<Status>("loading");
  const [paste, setPaste] = useState<Paste | null>(null);
  const [copyState, setCopyState] = useState<CopyState>("idle");

  useEffect(() => {
    let active = true;
    setStatus("loading");

    async function load(): Promise<void> {
      try {
        const loaded = await api.getPaste(slug);
        if (!active) return;
        setPaste(loaded);
        setStatus("ok");
      } catch (err) {
        if (!active) return;
        setStatus(err instanceof ApiError && err.status === 404 ? "notfound" : "error");
      }
    }

    void load();

    return () => {
      active = false;
    };
  }, [slug]);

  const copy = async () => {
    if (!paste) return;
    try {
      // Throws on insecure origins, where `clipboard` is undefined entirely.
      await navigator.clipboard.writeText(paste.content);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  useEffect(() => {
    if (copyState === "idle") return;
    const timer = window.setTimeout(() => setCopyState("idle"), 1500);
    return () => window.clearTimeout(timer);
  }, [copyState]);

  return (
    <main className="container">
      <header className="topbar">
        <h1>
          <Link to="/">Pastry</Link>
        </h1>
      </header>

      <div role="status" aria-live="polite">
        {status === "loading" && <p className="muted">Loading…</p>}
        {status === "notfound" && <p className="error">Paste not found (it may have expired).</p>}
        {status === "error" && <p className="error">Something went wrong.</p>}
      </div>

      {status === "ok" && paste && (
        <>
          <div className="paste-meta">
            <code className="slug">{paste.slug}</code>
            <div className="spacer" />
            <button
              type="button"
              className="link"
              onClick={() => void copy()}
              aria-label="Copy paste content"
            >
              {COPY_LABEL[copyState]}
            </button>
          </div>
          <p className="sr-only" role="status" aria-live="polite">
            {copyState === "copied" ? "Paste content copied to the clipboard." : ""}
            {copyState === "failed" ? "Could not copy to the clipboard." : ""}
          </p>
          <pre className="paste-body">{paste.content}</pre>
        </>
      )}
    </main>
  );
}
