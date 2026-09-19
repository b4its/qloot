import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    include: ["tests/**/*.{test,spec}.{js,ts}"],
    environment: "jsdom",
    environmentOptions: {
      jsdom: { url: "http://localhost:3000" },
    },
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
  resolve: {
    alias: {
      $lib: new URL("./src/lib", import.meta.url).pathname,
      $app: new URL("./tests/stubs/app", import.meta.url).pathname,
    },
  },
});
