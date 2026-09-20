import "@testing-library/jest-dom/vitest";

// jsdom may not provide localStorage depending on the origin; install a
// minimal in-memory implementation when missing so store tests are stable.
if (typeof globalThis.localStorage === "undefined" || globalThis.localStorage === null) {
  const store = new Map<string, string>();
  const fakeStorage: Storage = {
    get length() {
      return store.size;
    },
    clear() {
      store.clear();
    },
    getItem(key: string) {
      return store.has(key) ? (store.get(key) as string) : null;
    },
    key(index: number) {
      return Array.from(store.keys())[index] ?? null;
    },
    removeItem(key: string) {
      store.delete(key);
    },
    setItem(key: string, value: string) {
      store.set(key, String(value));
    },
  };
  Object.defineProperty(globalThis, "localStorage", { value: fakeStorage, configurable: true });
  if (typeof window !== "undefined") {
    Object.defineProperty(window, "localStorage", { value: fakeStorage, configurable: true });
  }
}

// jsdom lacks matchMedia; the theme store relies on it.
if (!window.matchMedia) {
  window.matchMedia = (query: string) =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as MediaQueryList;
}

// jsdom lacks IntersectionObserver; components use it for reveal animations.
if (!("IntersectionObserver" in window)) {
  class MockIntersectionObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
    takeRecords() {
      return [];
    }
    root = null;
    rootMargin = "";
    thresholds = [];
  }
  Object.defineProperty(window, "IntersectionObserver", {
    value: MockIntersectionObserver,
    configurable: true,
  });
  Object.defineProperty(globalThis, "IntersectionObserver", {
    value: MockIntersectionObserver,
    configurable: true,
  });
}

// jsdom lacks requestAnimationFrame in some environments.
if (typeof window.requestAnimationFrame === "undefined") {
  window.requestAnimationFrame = (cb: FrameRequestCallback) =>
    setTimeout(() => cb(performance.now()), 0) as unknown as number;
  window.cancelAnimationFrame = (id: number) => clearTimeout(id);
}
