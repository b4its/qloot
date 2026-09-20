import adapter from "@sveltejs/adapter-node";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ out: "build" }),
    alias: {
      $lib: "./src/lib",
      // Route groups `(landing)` / `(site)` contain parentheses, which break
      // bare relative imports in tooling (vite import analysis / tsc). Expose
      // them through clean aliases instead.
      $routes: "./src/routes",
      "$routes-landing": "./src/routes/(landing)",
      "$routes-site": "./src/routes/(site)",
    },
  },
};

export default config;
