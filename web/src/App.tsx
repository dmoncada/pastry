import { bootstrapAuth } from "@/api";
import { Callback } from "@/routes/Callback";
import { Home } from "@/routes/Home";
import { PastePage } from "@/routes/PastePage";
import { useEffect } from "react";
import { Link, Route, Routes } from "react-router-dom";

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

export function App(): JSX.Element {
  // Silently restore the session from the refresh cookie on load (the access token is
  // memory-only and gone after a reload). Idempotent — bootstrapAuth self-guards.
  useEffect(() => {
    void bootstrapAuth();
  }, []);

  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/p/:slug" element={<PastePage />} />
      <Route path="/callback" element={<Callback />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
