// @vitest-environment jsdom
import { describe, it, expect } from "vitest";
import attemptSrc from "$routes-site/exams/[examId]/attempt/+page.svelte?raw";

describe("exam telemetry disclosure (W5)", () => {
  it("discloses what is monitored before it happens", () => {
    expect(attemptSrc).toContain('data-role="telemetry-notice"');
    expect(attemptSrc).toMatch(/berpindah tab/i);
    expect(attemptSrc).toMatch(/kehilangan fokus/i);
    expect(attemptSrc).toMatch(/paste/i);
  });

  it("clarifies telemetry is context, not automatic proof", () => {
    expect(attemptSrc).toMatch(/bukan bukti otomatis/i);
    expect(attemptSrc).toMatch(/ditinjau ulang/i);
  });

  it("is dismissible and remembered per exam within the session", () => {
    expect(attemptSrc).toContain("dismissTelemetryNotice");
    expect(attemptSrc).toContain("sessionStorage.setItem(`qloot-telemetry-acked:");
    expect(attemptSrc).toContain("sessionStorage.getItem(`qloot-telemetry-acked:");
  });
});
