/**
 * Minimal flat ESLint config.
 *
 * TypeScript correctness is enforced by `npm run check` (svelte-check with
 * strict TS) and Svelte by the Svelte compiler. ESLint here covers plain
 * JavaScript files only and is kept dependency-light for reproducible CI.
 */
export default [
  {
    ignores: [
      ".svelte-kit/**",
      "build/**",
      "node_modules/**",
      "tests/e2e/**",
      "playwright-report/**",
      "test-results/**",
      "vitest.config.ts",
      "playwright.config.ts",
      "tailwind.config.ts",
      "vite.config.ts",
      "svelte.config.js",
      "postcss.config.js",
      "eslint.config.js",
    ],
  },
  {
    files: ["**/*.js", "**/*.mjs", "**/*.cjs"],
    languageOptions: {
      ecmaVersion: 2022,
      sourceType: "module",
    },
    rules: {
      "no-unused-vars": ["warn", { argsIgnorePattern: "^_", varsIgnorePattern: "^_" }],
      "no-undef": "off",
    },
  },
];
