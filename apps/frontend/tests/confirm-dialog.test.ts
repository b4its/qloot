// @vitest-environment jsdom
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/svelte";
import ConfirmDialog from "$lib/components/ConfirmDialog.svelte";

describe("ConfirmDialog", () => {
  it("renders the title, description and hint with an accessible modal role", () => {
    render(ConfirmDialog, {
      props: {
        title: "Hapus Data",
        description: "Data akan dihapus permanen.",
        hint: "Tindakan ini tidak dapat dibatalkan.",
        onConfirm: vi.fn(),
        close: vi.fn(),
      },
    });
    const dialog = screen.getByRole("dialog");
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByText("Hapus Data")).toBeTruthy();
    expect(screen.getByText("Data akan dihapus permanen.")).toBeTruthy();
    expect(screen.getByText("Tindakan ini tidak dapat dibatalkan.")).toBeTruthy();
    cleanup();
  });

  it("invokes onConfirm when the confirm button is clicked", async () => {
    const onConfirm = vi.fn();
    render(ConfirmDialog, {
      props: { title: "Konfirmasi", onConfirm, close: vi.fn() },
    });
    await fireEvent.click(document.querySelector('[data-role="confirm-action"]')!);
    expect(onConfirm).toHaveBeenCalledOnce();
    cleanup();
  });

  it("invokes close when the cancel button is clicked", async () => {
    const close = vi.fn();
    render(ConfirmDialog, {
      props: { title: "Konfirmasi", onConfirm: vi.fn(), close },
    });
    await fireEvent.click(screen.getByRole("button", { name: "Batal" }));
    expect(close).toHaveBeenCalledOnce();
    cleanup();
  });

  it("renders an optional reason textarea bound to the reason prop", () => {
    render(ConfirmDialog, {
      props: {
        title: "Cabut",
        reason: "",
        reasonLabel: "Alasan (opsional)",
        reasonPlaceholder: "mis. kesalahan",
        onConfirm: vi.fn(),
        close: vi.fn(),
      },
    });
    expect(screen.getByLabelText("Alasan (opsional)")).toBeTruthy();
    cleanup();
  });

  it("emits reason changes back to the parent via onReason", async () => {
    const onReason = vi.fn();
    render(ConfirmDialog, {
      props: { title: "Cabut", reason: "", onReason, onConfirm: vi.fn(), close: vi.fn() },
    });
    await fireEvent.input(screen.getByLabelText("Alasan (opsional)"), {
      target: { value: "alamat salah" },
    });
    expect(onReason).toHaveBeenCalledWith("alamat salah");
    cleanup();
  });

  it("uses a custom confirmRole for the confirm button", () => {
    render(ConfirmDialog, {
      props: { title: "T", confirmRole: "confirm-custom", onConfirm: vi.fn(), close: vi.fn() },
    });
    expect(document.querySelector('[data-role="confirm-custom"]')).toBeTruthy();
    expect(document.querySelector('[data-role="confirm-action"]')).toBeNull();
    cleanup();
  });

  it("invokes close when Escape is pressed on the window", async () => {
    const close = vi.fn();
    render(ConfirmDialog, {
      props: { title: "T", onConfirm: vi.fn(), close },
    });
    await fireEvent.keyDown(window, { key: "Escape" });
    expect(close).toHaveBeenCalledOnce();
    cleanup();
  });

  it("invokes close when clicking outside the dialog card (on backdrop overlay)", async () => {
    const close = vi.fn();
    render(ConfirmDialog, {
      props: { title: "T", onConfirm: vi.fn(), close },
    });
    const backdrop = document.querySelector('[role="presentation"]') as HTMLElement;
    expect(backdrop).toBeTruthy();
    await fireEvent.click(backdrop);
    expect(close).toHaveBeenCalledOnce();
    cleanup();
  });
});
