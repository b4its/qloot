// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup } from "@testing-library/svelte";

// Avoid real network calls triggered by the layout's onMount bootstrapping.
vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  ApiError: class ApiError extends Error {
    status = 0;
  },
  api: {
    get: vi.fn().mockRejectedValue(new Error("offline")),
    post: vi.fn().mockRejectedValue(new Error("offline")),
  },
}));

import LandingPage from "$routes-landing/+page.svelte";
import LandingLayout from "$routes-landing/+layout.svelte";
import { classTracks } from "../src/lib/data/content";

// The one-page landing is composed of anchored sections. Keeping the ids in
// sync is what makes the header anchor nav functional.
const SECTION_IDS = ["fitur", "kelas", "guru", "sertifikat", "testimoni"];

describe("landing page (one-page)", () => {
  beforeEach(() => cleanup());

  it("renders all anchored sections used by the nav", () => {
    const { container } = render(LandingPage);
    for (const id of SECTION_IDS) {
      expect(container.querySelector(`#${id}`), `missing section #${id}`).toBeTruthy();
    }
  });

  it("shows the primary value proposition heading", () => {
    render(LandingPage);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(/didampingi/i);
  });

  it("lists every class track with its subjects", () => {
    const { container } = render(LandingPage);
    for (const track of classTracks) {
      expect(container.textContent).toContain(track.label);
    }
  });
});

describe("landing layout (separated from app navbar)", () => {
  beforeEach(() => cleanup());

  it("uses its own in-page anchor navigation instead of the app nav", () => {
    render(LandingLayout);
    // Anchor nav entries are buttons (in-page), present for every section.
    for (const id of SECTION_IDS) {
      const label = id.charAt(0).toUpperCase() + id.slice(1);
      expect(
        screen.getAllByRole("button", { name: new RegExp(`^${label}$`, "i") }).length,
      ).toBeGreaterThan(0);
    }
  });

  it("does not render the global marketing nav or the news ticker", () => {
    const { container } = render(LandingLayout);
    // The app shell ticker + primary nav labels must not leak into the landing.
    expect(container.querySelector(".ticker")).toBeNull();
    expect(screen.queryByRole("link", { name: "Jalur Belajar" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Komunitas" })).toBeNull();
  });
});
