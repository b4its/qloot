import { defineConfig } from "vitest/config";
import { svelte } from "@sveltejs/vite-plugin-svelte";

export default defineConfig({
  plugins: [svelte({ hot: false })],
  test: {
    include: ["tests/**/*.{test,spec}.{js,ts}"],
    exclude: ["tests/e2e/**", "node_modules/**"],
    environment: "jsdom",
    environmentOptions: {
      jsdom: { url: "http://localhost:3000" },
    },
    globals: true,
    setupFiles: ["./tests/setup.ts"],
  },
  resolve: {
    // `browser` condition makes Svelte resolve its client runtime so
    // @testing-library/svelte can mount components under jsdom.
    conditions: ["browser"],
    alias: {
      $lib: new URL("./src/lib", import.meta.url).pathname,
      $app: new URL("./tests/stubs/app", import.meta.url).pathname,
      "$routes-landing": new URL("./src/routes/(landing)", import.meta.url).pathname,
      "$routes-site": new URL("./src/routes/(site)", import.meta.url).pathname,
    },
  },
});
