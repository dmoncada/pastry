import { api, ApiError } from "@/api";
import type { Paste } from "@/types";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";

type Status = "loading" | "ok" | "notfound" | "error";

export function PastePage(): JSX.Element {
  const { slug = "" } = useParams();
  const [status, setStatus] = useState<Status>("loading");
  const [paste, setPaste] = useState<Paste | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    let active = true;
    setStatus("loading");
    api
      .getPaste(slug)
      .then((p) => {
        if (!active) return;
        setPaste(p);
        setStatus("ok");
      })
      .catch((err) => {
        if (!active) return;
        setStatus(err instanceof ApiError && err.status === 404 ? "notfound" : "error");
      });
    return () => {
      active = false;
    };
  }, [slug]);

  const copy = () => {
    if (!paste) return;
    void navigator.clipboard?.writeText(paste.content);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1500);
  };

  return (
    <main className="container">
      <header className="topbar">
        <h1>
          <Link to="/">Pastry</Link>
        </h1>
      </header>

      {status === "loading" && <p className="muted">Loading…</p>}
      {status === "notfound" && <p className="error">Paste not found (it may have expired).</p>}
      {status === "error" && <p className="error">Something went wrong.</p>}

      {status === "ok" && paste && (
        <>
          <div className="paste-meta">
            <code className="slug">{paste.slug}</code>
            <div className="spacer" />
            <button className="link" onClick={copy}>
              {copied ? "copied!" : "copy"}
            </button>
          </div>
          <pre className="paste-body">{paste.content}</pre>
        </>
      )}
    </main>
  );
}
