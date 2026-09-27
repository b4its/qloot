// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

vi.mock("$app/navigation", () => ({ goto: vi.fn() }));

import CareersPage from "$routes-site/careers/+page.svelte";

beforeEach(() => cleanup());

describe("careers — type/remote filters and search", () => {
  it("renders all roles with type chips", async () => {
    render(CareersPage);
    expect(screen.getByText("Senior Frontend Engineer")).toBeTruthy();
    expect(screen.getByRole("button", { name: /Semua \(3\)/ })).toBeTruthy();
    expect(screen.getByRole("button", { name: /Penuh waktu \(2\)/ })).toBeTruthy();
  });

  it("filters by employment type", async () => {
    render(CareersPage);
    await fireEvent.click(screen.getByRole("button", { name: /Kontrak \(1\)/ }));
    await waitFor(() => expect(screen.queryByText("Senior Frontend Engineer")).toBeNull());
    expect(screen.getByText("Content Creator (Data & AI)")).toBeTruthy();
  });

  it("filters to remote-only roles", async () => {
    render(CareersPage);
    await fireEvent.click(screen.getByRole("button", { name: /Remote/ }));
    await waitFor(() => expect(screen.queryByText("Learning Experience Designer")).toBeNull());
    // Senior Frontend Engineer and Content Creator are both remote.
    expect(screen.getByText("Senior Frontend Engineer")).toBeTruthy();
  });

  it("searches roles and shows an empty state with reset", async () => {
    render(CareersPage);
    const input = screen.getByLabelText("Cari posisi") as HTMLInputElement;
    await fireEvent.input(input, { target: { value: "zzz-no-match" } });
    await waitFor(() => expect(screen.getByText(/Tidak ada posisi yang cocok/)).toBeTruthy());
    expect(screen.getByRole("button", { name: "Reset Filter" })).toBeTruthy();
  });
});
