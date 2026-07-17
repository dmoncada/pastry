import { completeLogin } from "@/api";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

export function Callback(): JSX.Element {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false);

  useEffect(() => {
    if (ran.current) return; // StrictMode double-invoke guard: exchange the code once
    ran.current = true;

    const code = params.get("code");
    const state = params.get("state");
    if (!code || !state) {
      setError("Missing code or state in callback.");
      return;
    }
    completeLogin(code, state)
      .then(() => navigate("/", { replace: true }))
      .catch((err) => setError(String(err)));
  }, [params, navigate]);

  return (
    <main className="container">
      {error ? (
        <>
          <p className="error">{error}</p>
          <p>
            <Link to="/">← back to Pastry</Link>
          </p>
        </>
      ) : (
        <p className="muted">Signing you in…</p>
      )}
    </main>
  );
}
