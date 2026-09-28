// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/svelte";
import SearchInput from "$lib/components/SearchInput.svelte";

describe("SearchInput", () => {
  it("renders a searchbox with the placeholder as the accessible name", () => {
    render(SearchInput, { props: { placeholder: "Cari pelajaran..." } });
    const input = screen.getByRole("searchbox", { name: "Cari pelajaran..." });
    expect(input).toBeTruthy();
    expect(input.getAttribute("type")).toBe("search");
    cleanup();
  });

  it("prefers an explicit label over the placeholder", () => {
    render(SearchInput, { props: { label: "Cari ujian", placeholder: "x" } });
    expect(screen.getByRole("searchbox", { name: "Cari ujian" })).toBeTruthy();
    cleanup();
  });

  it("fires oninput on every keystroke", async () => {
    const oninput = vi.fn();
    render(SearchInput, { props: { value: "", oninput } });
    await fireEvent.input(screen.getByRole("searchbox"), { target: { value: "ab" } });
    expect(oninput).toHaveBeenCalled();
    cleanup();
  });

  it("shows a clear button only when there is text and clears it", async () => {
    const onclear = vi.fn();
    render(SearchInput, { props: { value: "", onclear } });
    expect(screen.queryByRole("button", { name: "Bersihkan pencarian" })).toBeNull();
    cleanup();

    render(SearchInput, { props: { value: "hello", onclear } });
    const clear = screen.getByRole("button", { name: "Bersihkan pencarian" });
    await fireEvent.click(clear);
    expect(onclear).toHaveBeenCalledOnce();
    expect((screen.getByRole("searchbox") as HTMLInputElement).value).toBe("");
    cleanup();
  });
});
