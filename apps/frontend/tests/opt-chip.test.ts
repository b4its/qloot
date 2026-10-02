// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";

const { apiGet } = vi.hoisted(() => ({ apiGet: vi.fn() }));
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  api: { get: (...args: unknown[]) => apiGet(...args) },
}));

import OptChip from "../src/lib/components/OptChip.svelte";
import { opt } from "../src/lib/stores/opt";

describe("OptChip component", () => {
  beforeEach(() => {
    opt.reset();
    apiGet.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the available OPT balance", async () => {
    opt.setBalance(1250);
    render(OptChip);

    expect(screen.getByText("1.250")).toBeTruthy();
    expect(screen.getByText("OPT")).toBeTruthy();
  });

  it("shows pending balance indicator when pending > 0", async () => {
    opt.setBalance(500, 50);
    render(OptChip);

    expect(screen.getByText("500")).toBeTruthy();
    expect(screen.getByText("50")).toBeTruthy();
    expect(screen.getByTitle("Menunggu konfirmasi")).toBeTruthy();
  });

  it("flashes difference badge when balance increases dynamically", async () => {
    opt.setBalance(100);
    render(OptChip);

    expect(screen.getByText("100")).toBeTruthy();
    expect(screen.queryByText("+50")).toBeNull();

    // Balance increments dynamically (e.g. from realtime WebSocket)
    opt.setBalance(150);

    // Should render the difference badge
    expect(await screen.findByText("+50")).toBeTruthy();
  });
});
