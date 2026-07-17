import { Callback } from "@/routes/Callback";
import { Home } from "@/routes/Home";
import { PastePage } from "@/routes/PastePage";
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
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/p/:slug" element={<PastePage />} />
      <Route path="/callback" element={<Callback />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  );
}
