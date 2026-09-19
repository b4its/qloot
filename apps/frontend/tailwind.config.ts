import type { Config } from "tailwindcss";

/**
 * QLoot design system — minimal + futuristic with subtle Web3 vibes.
 *
 * Colors are driven by CSS variables (see src/app.css) so light/dark themes
 * are first-class, not inverted. The accent palette is shared across themes.
 */
export default {
  content: ["./src/**/*.{html,js,svelte,ts}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Semantic surfaces (theme-aware via CSS vars).
        bg: "rgb(var(--bg) / <alpha-value>)",
        surface: "rgb(var(--surface) / <alpha-value>)",
        elevated: "rgb(var(--elevated) / <alpha-value>)",
        ink: "rgb(var(--ink) / <alpha-value>)",
        ink2: "rgb(var(--ink2) / <alpha-value>)",
        muted: "rgb(var(--muted) / <alpha-value>)",
        line: "rgb(var(--line) / <alpha-value>)",

        // Web3 accents (same in both themes).
        primary: {
          DEFAULT: "#5B48FF",
          50: "#EEECFF",
          100: "#DEDAFF",
          200: "#C4BCFF",
          300: "#A99EFF",
          400: "#8B7DFF",
          500: "#5B48FF",
          600: "#4838D9",
          700: "#372BB0",
          800: "#2A2187",
          900: "#1E1760",
        },
        secondary: { DEFAULT: "#00E5A8", 500: "#00E5A8", 600: "#00C08C" },
        tertiary: { DEFAULT: "#FF5CAA", 500: "#FF5CAA" },
        highlight: { DEFAULT: "#FFD166", 500: "#FFD166" },
      },
      fontFamily: {
        display: ['"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"Inter"', "system-ui", "-apple-system", "Segoe UI", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        caption: ["11px", { lineHeight: "1.4", letterSpacing: "0.14em" }],
      },
      borderRadius: {
        sm: "12px",
        card: "18px",
        hero: "24px",
      },
      boxShadow: {
        // Light elevation.
        soft: "0 1px 0 rgba(0,0,0,.02), 0 20px 60px -30px rgba(0,0,0,.15)",
        // Dark elevation with a faint indigo glow.
        glowcard: "0 0 0 1px rgba(255,255,255,.04), 0 30px 80px -40px rgba(91,72,255,.35)",
        glow: "0 0 30px -6px rgba(91,72,255,.55)",
        glowmint: "0 0 30px -6px rgba(0,229,168,.5)",
      },
      backgroundImage: {
        "grad-signature": "linear-gradient(135deg, #5B48FF 0%, #00E5A8 100%)",
        "grad-tertiary": "linear-gradient(135deg, #FF5CAA 0%, #5B48FF 100%)",
        "grad-border":
          "linear-gradient(135deg, rgba(91,72,255,.9), rgba(0,229,168,.9), rgba(255,92,170,.7))",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.22, 1, 0.36, 1)",
      },
      keyframes: {
        aurora: {
          "0%,100%": { transform: "translate3d(0,0,0) scale(1)" },
          "50%": { transform: "translate3d(2%,-3%,0) scale(1.08)" },
        },
        marquee: {
          "0%": { transform: "translateX(0)" },
          "100%": { transform: "translateX(-50%)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
        spinSlow: { to: { transform: "rotate(360deg)" } },
        riseIn: {
          from: { opacity: "0", transform: "translateY(20px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        aurora: "aurora 18s ease-in-out infinite",
        marquee: "marquee 40s linear infinite",
        shimmer: "shimmer 2.4s linear infinite",
        "spin-slow": "spinSlow 6s linear infinite",
        "rise-in": "riseIn .5s cubic-bezier(0.22,1,0.36,1) both",
      },
    },
  },
} satisfies Config;
