import { bootstrapAuth } from "@/api";
import { Callback } from "@/routes/Callback";
import { Home } from "@/routes/Home";
import { PastePage } from "@/routes/PastePage";
import { useEffect } from "react";
import { Link, Route, Routes, useParams } from "react-router-dom";

const SLUG_RE = /^[0-9A-HJKMNP-TV-Z]{20}$/i;

function NotFound(): JSX.Element {
  return (
    <main className="container">
      <h1>Not found</h1>
      <p>
        <Link to="/">← back to Pastry</Link>
      </p>
    </main>
  );
}

function PasteRoute(): JSX.Element {
  const { slug } = useParams();
  return slug && SLUG_RE.test(slug) ? <PastePage /> : <NotFound />;
}

export function App(): JSX.Element {
  // Silently restore the session from the refresh cookie on load (the access token is
  // memory-only and gone after a reload). Idempotent — bootstrapAuth self-guards.
  useEffect(() => {
    void bootstrapAuth();
  }, []);

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/:slug" element={<PasteRoute />} />
      <Route path="/callback" element={<Callback />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
