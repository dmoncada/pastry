import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "@/api";
import { Home } from "@/routes/Home";
import type { Paste } from "@/types";

vi.mock("@/api", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/api")>();
  return {
    ...actual,
    api: {
      me: vi.fn(),
      listPastes: vi.fn(),
      createPaste: vi.fn(),
      updatePaste: vi.fn(),
      deletePaste: vi.fn(),
      getPaste: vi.fn(),
    },
    beginLogin: vi.fn(),
    logout: vi.fn(),
  };
});

const mockApi = vi.mocked(api);

function paste(over: Partial<Paste> = {}): Paste {
  return {
    slug: "ABC123",
    content: "hello world\nsecond line",
    owner_github_id: "dev-user",
    created_at: "2026-07-16T00:00:00Z",
    updated_at: "2026-07-16T00:00:00Z",
    expires_at: null,
    size: 11,
    ...over,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  mockApi.me.mockResolvedValue({ github_id: "dev-user", login: "dev-user" });
  localStorage.setItem("pastry.access", "test-access-token"); // signed in: enables the editor
});

afterEach(() => {
  localStorage.clear();
});

describe("Home", () => {
  it("renders the paste list", async () => {
    mockApi.listPastes.mockResolvedValue([paste()]);
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Home />
      </MemoryRouter>,
    );
    expect(await screen.findByText("ABC123")).toBeInTheDocument();
    expect(screen.getByText("hello world")).toBeInTheDocument(); // only first line
  });

  it("creates a paste from the editor", async () => {
    mockApi.listPastes.mockResolvedValue([]);
    mockApi.createPaste.mockResolvedValue(paste({ slug: "NEW" }));
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <Home />
      </MemoryRouter>,
    );
    await waitFor(() => expect(mockApi.listPastes).toHaveBeenCalled());

    await userEvent.type(screen.getByLabelText("paste content"), "brand new paste");
    await userEvent.click(screen.getByRole("button", { name: "Create paste" }));

    await waitFor(() => expect(mockApi.createPaste).toHaveBeenCalledWith("brand new paste", ""));
  });
});
