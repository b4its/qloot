// @vitest-environment jsdom
import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, cleanup, waitFor, fireEvent } from "@testing-library/svelte";

const mockGet = vi.fn();
const mockPost = vi.fn();

vi.mock("../src/lib/api/client", () => ({
  API_BASE: "http://localhost:8000",
  API_PREFIX: "/api/v1",
  ApiError: class ApiError extends Error {
    status: number;
    code: string;
    detail: unknown;
    constructor(status: number, code: string, message: string, detail?: unknown) {
      super(message);
      this.status = status;
      this.code = code;
      this.detail = detail;
    }
  },
  api: {
    get: (...args: unknown[]) => mockGet(...args),
    post: (...args: unknown[]) => mockPost(...args),
    put: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

import AssistantPage from "$routes-site/assistant/+page.svelte";
import { ApiError } from "../src/lib/api/client";

beforeEach(() => {
  cleanup();
  vi.clearAllMocks();
  // Default mocks
  mockGet.mockImplementation((url: string) => {
    if (url === "/career/assistant/conversations") {
      return Promise.resolve([]);
    }
    if (url === "/career/assistant/quota") {
      return Promise.resolve({
        ort_balance: 5,
        free_requests_remaining: 0,
        can_chat: true,
      });
    }
    return Promise.resolve([]);
  });
});

describe("assistant AI credits and chat locking", () => {
  it("locks chat and displays out-of-credits message in transcript on mount when quota is 0", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/career/assistant/conversations") return Promise.resolve([]);
      if (url === "/career/assistant/quota") {
        return Promise.resolve({
          ort_balance: 0,
          free_requests_remaining: 0,
          can_chat: false,
        });
      }
      return Promise.resolve([]);
    });

    render(AssistantPage);

    // Verify out-of-credits message appears in chat log
    await waitFor(() => {
      const log = document.querySelector('[role="log"]');
      expect(log).toBeTruthy();
      expect(log?.textContent).toContain(
        "Kredit AI (ORT) habis. Tukar OPT menjadi ORT di halaman dompet untuk melanjutkan.",
      );
    });

    // Check link to wallet inside the chat transcript
    const log = document.querySelector('[role="log"]');
    const walletLink = log?.querySelector('a[href="/wallet"]');
    expect(walletLink).toBeTruthy();
    expect(walletLink?.textContent).toContain("halaman dompet");

    // Check input is disabled and has warning placeholder
    const input = screen.getByLabelText(/pertanyaan untuk asisten qlu/i) as HTMLInputElement;
    expect(input.disabled).toBe(true);
    expect(input.placeholder).toContain("Kredit AI (ORT) habis");

    // Check Kirim button is disabled
    const sendBtn = screen.getByRole("button", { name: /^kirim$/i }) as HTMLButtonElement;
    expect(sendBtn.disabled).toBe(true);

    // Check suggestion buttons are disabled
    const suggestionBtns = screen.getAllByRole("button", { name: /snbp|prospek|teknik|ipa/i });
    expect(suggestionBtns.length).toBeGreaterThan(0);
    for (const btn of suggestionBtns) {
      expect((btn as HTMLButtonElement).disabled).toBe(true);
    }
  });

  it("locks chat and injects out-of-credits message when stream returns HTTP 402", async () => {
    // Start with 1 ORT available
    mockGet.mockImplementation((url: string) => {
      if (url === "/career/assistant/conversations") return Promise.resolve([]);
      if (url === "/career/assistant/quota") {
        return Promise.resolve({
          ort_balance: 1,
          free_requests_remaining: 0,
          can_chat: true,
        });
      }
      return Promise.resolve([]);
    });

    // Mock fetch to simulate 402 Payment Required on stream
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 402,
      body: null,
    } as unknown as Response);

    try {
      render(AssistantPage);

      const input = screen.getByLabelText(/pertanyaan untuk asisten qlu/i) as HTMLInputElement;
      await waitFor(() => expect(input.disabled).toBe(false));

      await fireEvent.input(input, { target: { value: "Mau tanya rekomendasi jurusan" } });
      const sendBtn = screen.getByRole("button", { name: /^kirim$/i });
      await fireEvent.click(sendBtn);

      // Verify the bot message in the chat log contains the out-of-credits message
      await waitFor(() => {
        const log = document.querySelector('[role="log"]');
        expect(log?.textContent).toContain(
          "Kredit AI (ORT) habis. Tukar OPT menjadi ORT di halaman dompet untuk melanjutkan.",
        );
      });

      // Verify chat controls become disabled
      expect(input.disabled).toBe(true);
      expect(sendBtn as HTMLButtonElement).toBeDisabled();
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("locks chat and injects out-of-credits message when JSON fallback returns 402 ApiError", async () => {
    // Start with 1 ORT available
    mockGet.mockImplementation((url: string) => {
      if (url === "/career/assistant/conversations") return Promise.resolve([]);
      if (url === "/career/assistant/quota") {
        return Promise.resolve({
          ort_balance: 1,
          free_requests_remaining: 0,
          can_chat: true,
        });
      }
      return Promise.resolve([]);
    });

    // Mock fetch to fail stream, triggering JSON fallback
    const originalFetch = globalThis.fetch;
    globalThis.fetch = vi.fn().mockRejectedValue(new Error("Network failed"));

    // JSON fallback throws 402 ApiError
    mockPost.mockRejectedValue(
      new ApiError(
        402,
        "payment_required",
        "Kredit AI (ORT) habis. Tukar OPT menjadi ORT di halaman dompet untuk melanjutkan.",
      ),
    );

    try {
      render(AssistantPage);

      const input = screen.getByLabelText(/pertanyaan untuk asisten qlu/i) as HTMLInputElement;
      await waitFor(() => expect(input.disabled).toBe(false));

      await fireEvent.input(input, { target: { value: "Halo asisten" } });
      const sendBtn = screen.getByRole("button", { name: /^kirim$/i });
      await fireEvent.click(sendBtn);

      // Verify message in chat log
      await waitFor(() => {
        const log = document.querySelector('[role="log"]');
        expect(log?.textContent).toContain(
          "Kredit AI (ORT) habis. Tukar OPT menjadi ORT di halaman dompet untuk melanjutkan.",
        );
      });

      // Input and send button disabled
      expect(input.disabled).toBe(true);
      expect(sendBtn as HTMLButtonElement).toBeDisabled();
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("preserves out-of-credits message and disabled state when clicking + Percakapan baru", async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === "/career/assistant/conversations") return Promise.resolve([]);
      if (url === "/career/assistant/quota") {
        return Promise.resolve({
          ort_balance: 0,
          free_requests_remaining: 0,
          can_chat: false,
        });
      }
      return Promise.resolve([]);
    });

    render(AssistantPage);

    await waitFor(() => {
      const log = document.querySelector('[role="log"]');
      expect(log?.textContent).toContain("Kredit AI (ORT) habis");
    });

    const newConvBtn = screen.getByRole("button", { name: /\+ percakapan baru/i });
    await fireEvent.click(newConvBtn);

    // Verify out-of-credits message is still present in chat log
    const log = document.querySelector('[role="log"]');
    expect(log?.textContent).toContain("Kredit AI (ORT) habis");

    // Input still disabled
    const input = screen.getByLabelText(/pertanyaan untuk asisten qlu/i) as HTMLInputElement;
    expect(input.disabled).toBe(true);
  });
});
