/// <reference types="vite/client" />

// `?raw` imports (used by source-level tests) return the file text as a string.
declare module "*?raw" {
  const content: string;
  export default content;
}
