import { describe, it, expect } from "vitest";
import { bpToPercent, shortHash, formatNumber, etherscanUrl } from "../src/lib/utils/format";

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
});
