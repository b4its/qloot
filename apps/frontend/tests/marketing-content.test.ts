// @vitest-environment jsdom
import { describe, it, expect } from "vitest";

// Raw source text of the public marketing pages (Vite `?raw` import — no Node
// runtime APIs needed). We assert on the copy itself so the pages describe the
// real class-based product: no paid courses, no "lifetime access" storefront
// copy, and About stats must be explicitly labelled illustrative. (UIX-01)
import faqSrc from "$routes-site/faq/+page.svelte?raw";
import aboutSrc from "$routes-site/about/+page.svelte?raw";
import contentSrc from "$lib/data/content.ts?raw";

const FORBIDDEN = [
  /akses selamanya/i,
  /akses seumur hidup/i,
  /pembayaran dilakukan/i,
  /beli kursus/i,
  // "kursus berbayar" is only wrong as a *claim*; the denial "tidak ada
  // kursus berbayar" is correct, so anchor on the claim phrasing.
  /untuk kursus berbayar/i,
];

describe("marketing pages match the class-based product model", () => {
  for (const [name, src] of [
    ["faq", faqSrc],
    ["about", aboutSrc],
  ] as const) {
    it(`${name} contains no paid-course/lifetime claims`, () => {
      for (const re of FORBIDDEN) {
        expect(re.test(src), `forbidden copy ${re} in ${name}`).toBe(false);
      }
    });
  }

  it("about page labels its headline stats as illustrative", () => {
    expect(aboutSrc.toLowerCase()).toContain("ilustratif");
  });

  it("content.ts states there are no paid courses", () => {
    expect(contentSrc.toLowerCase()).toContain("no paid courses");
  });
});
