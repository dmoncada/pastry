import { App } from "@/App";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

vi.mock("@/api", () => ({ bootstrapAuth: vi.fn() }));

function renderAt(path: string) {
  return render(
    <MemoryRouter
      initialEntries={[path]}
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <App />
    </MemoryRouter>,
  );
}

describe("App routes", () => {
  it("keeps the OAuth callback reachable", () => {
    renderAt("/callback");
    expect(screen.getByText(/Missing code or state/i)).toBeInTheDocument();
  });

  it.each(["/api", "/raw", "/not-a-slug"])(
    "sends reserved and invalid root path %s to the app 404 page",
    (path) => {
      renderAt(path);
      expect(screen.getByRole("heading", { name: "Not found" })).toBeInTheDocument();
    },
  );
});
