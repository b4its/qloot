import { describe, it, expect } from "vitest";
import {
  bpToPercent,
  shortHash,
  formatNumber,
  etherscanUrl,
  statusLabel,
  relativeTime,
  paginate,
} from "../src/lib/utils/format";

describe("format utils", () => {
  it("converts basis points to percent", () => {
    expect(bpToPercent(10000)).toBe("100.0%");
    expect(bpToPercent(8750)).toBe("87.5%");
    expect(bpToPercent(0)).toBe("0.0%");
    expect(bpToPercent(null)).toBe("—");
  });

  it("shortens hashes", () => {
    expect(shortHash("0x1234567890abcdef")).toMatch(/^0x1234…cdef$/);
    expect(shortHash(null)).toBe("—");
  });

  it("formats numbers with grouping", () => {
    expect(formatNumber(1234567)).toBe("1,234,567");
    expect(formatNumber(null)).toBe("0");
  });

  it("builds etherscan urls only for sepolia", () => {
    const hash = "0xabc";
    expect(etherscanUrl(hash, 11155111)).toContain("sepolia.etherscan.io");
    expect(etherscanUrl(hash, 31337)).toBeNull();
    expect(etherscanUrl(null, 11155111)).toBeNull();
  });

  it("maps internal statuses to Indonesian labels", () => {
    expect(statusLabel("open")).toBe("Terbuka");
    expect(statusLabel("finalized")).toBe("Final");
    expect(statusLabel("in_review")).toBe("Dalam tinjauan");
    // Case-insensitive and falls back to the raw value for unknown statuses.
    expect(statusLabel("PENDING")).toBe("Menunggu");
    expect(statusLabel("custom_state")).toBe("custom_state");
    expect(statusLabel(null)).toBe("—");
  });

  it("renders relative time in Indonesian", () => {
    const ago = (ms: number) => new Date(Date.now() - ms).toISOString();
    expect(relativeTime(ago(5 * 1000))).toContain("dtk lalu");
    expect(relativeTime(ago(5 * 60 * 1000))).toContain("mnt lalu");
    expect(relativeTime(ago(5 * 60 * 60 * 1000))).toContain("jam lalu");
    expect(relativeTime(ago(5 * 24 * 60 * 60 * 1000))).toContain("hari lalu");
    expect(relativeTime(null)).toBe("—");
  });

  it("paginates an in-memory list into 1-indexed pages", () => {
    const items = [1, 2, 3, 4, 5, 6, 7];
    expect(paginate(items, 1, 3)).toEqual([1, 2, 3]);
    expect(paginate(items, 2, 3)).toEqual([4, 5, 6]);
    expect(paginate(items, 3, 3)).toEqual([7]);
    // Out-of-range pages yield an empty slice rather than throwing.
    expect(paginate(items, 4, 3)).toEqual([]);
    expect(paginate(items, 0, 3)).toEqual([1, 2, 3]);
    expect(paginate([], 1, 10)).toEqual([]);
  });
});
