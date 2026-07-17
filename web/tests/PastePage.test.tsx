import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { api, ApiError } from "@/api";
import { PastePage } from "@/routes/PastePage";

vi.mock("@/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api")>();
  return { ...actual, api: { ...actual.api, getPaste: vi.fn() } };
});

const mockApi = vi.mocked(api);

function renderAt(slug: string) {
  return render(
    <MemoryRouter
      initialEntries={[`/p/${slug}`]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <Routes>
        <Route path="/p/:slug" element={<PastePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("PastePage", () => {
  it("shows the paste content", async () => {
    mockApi.getPaste.mockResolvedValue({
      slug: "ABC",
      content: "public content here",
      owner_github_id: "u",
      created_at: "",
      updated_at: "",
      expires_at: null,
      size: 19,
    });
    renderAt("ABC");
    expect(await screen.findByText("public content here")).toBeInTheDocument();
  });

  it("shows not-found for a 404", async () => {
    mockApi.getPaste.mockRejectedValue(new ApiError("paste not found", 404));
    renderAt("MISSING");
    expect(await screen.findByText(/not found/i)).toBeInTheDocument();
  });
});
