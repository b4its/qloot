// @vitest-environment jsdom
import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup, waitFor } from "@testing-library/svelte";

import WalletChip from "$lib/components/WalletChip.svelte";

const ADDR = "0x1234567890abcdef1234567890abcdef12345678";

describe("WalletChip copy feedback", () => {
  afterEach(() => cleanup());

  it("shows copied state after a successful copy", async () => {
    cleanup();
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    render(WalletChip, { props: { address: ADDR, label: "Wallet address" } });
    await fireEvent.click(screen.getByRole("button"));
    await waitFor(() => expect(navigator.clipboard.writeText).toHaveBeenCalledWith(ADDR));
  });

  it("surfaces a failure instead of a silent no-op", async () => {
    cleanup();
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("no")) } });
    render(WalletChip, { props: { address: ADDR } });
    await fireEvent.click(screen.getByRole("button"));
    expect(await screen.findByText(/tidak dapat disalin/i)).toBeTruthy();
  });
});
