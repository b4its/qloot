// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import attemptSrc from "$routes-site/exams/[examId]/attempt/+page.svelte?raw";

// Collapse whitespace so assertions survive Prettier line-wrapping of copy.
const flat = attemptSrc.replace(/\s+/g, " ");

describe("exam telemetry disclosure (W5)", () => {
  it("discloses what is monitored before it happens", () => {
    expect(attemptSrc).toContain('data-role="telemetry-notice"');
    expect(flat).toMatch(/berpindah tab/i);
    expect(flat).toMatch(/kehilangan fokus/i);
    expect(flat).toMatch(/paste/i);
  });

  it("clarifies telemetry is context, not automatic proof", () => {
    expect(flat).toMatch(/bukan bukti otomatis/i);
    expect(flat).toMatch(/ditinjau ulang/i);
  });

  it("is dismissible and remembered per exam within the session", () => {
    expect(attemptSrc).toContain("dismissTelemetryNotice");
    expect(attemptSrc).toContain("sessionStorage.setItem(`qloot-telemetry-acked:");
    expect(attemptSrc).toContain("sessionStorage.getItem(`qloot-telemetry-acked:");
  });
});
