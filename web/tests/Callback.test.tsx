import { ApiError, completeLogin } from "@/api";
import { Callback } from "@/routes/Callback";
import { render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api")>();
  return { ...actual, completeLogin: vi.fn() };
});

const mockCompleteLogin = vi.mocked(completeLogin);

function renderAt(query: string, { strict = false } = {}) {
  const tree = (
    <MemoryRouter
      initialEntries={[`/callback${query}`]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/callback" element={<Callback />} />
        <Route path="/" element={<p>home page</p>} />
      </Routes>
    </MemoryRouter>
  );
  return render(strict ? <React.StrictMode>{tree}</React.StrictMode> : tree);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("Callback", () => {
  it("exchanges the code and redirects home", async () => {
    mockCompleteLogin.mockResolvedValue();
    renderAt("?code=abc&state=xyz");

    expect(await screen.findByText("home page")).toBeInTheDocument();
    expect(mockCompleteLogin).toHaveBeenCalledWith("abc", "xyz");
  });

  it("surfaces an exchange failure instead of redirecting", async () => {
    // Matches what completeLogin actually throws — errorText only surfaces ApiError
    // messages, and shows a generic string for anything else.
    mockCompleteLogin.mockRejectedValue(new ApiError("OAuth state mismatch"));
    renderAt("?code=abc&state=forged");

    expect(await screen.findByText(/OAuth state mismatch/)).toBeInTheDocument();
    expect(screen.queryByText("home page")).not.toBeInTheDocument();
  });

  it("reports a callback missing code or state", async () => {
    renderAt("?code=abc");

    expect(await screen.findByText(/Missing code or state/)).toBeInTheDocument();
    expect(mockCompleteLogin).not.toHaveBeenCalled();
  });

  it("exchanges the code only once under StrictMode double-invoke", async () => {
    mockCompleteLogin.mockResolvedValue();
    renderAt("?code=abc&state=xyz", { strict: true });

    expect(await screen.findByText("home page")).toBeInTheDocument();
    expect(mockCompleteLogin).toHaveBeenCalledTimes(1);
  });
});
