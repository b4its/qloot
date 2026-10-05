import type { Config } from "tailwindcss";

/**
 * QLoot design system — blue-first cyberpunk learning command center.
 *
 * Near-black blue surfaces with electric-blue actions, cyan data signals,
 * yellow rewards, hot magenta and critical red. Colors are driven by CSS variables
 * (see src/app.css) so the light ("day cycle") and dark ("night city")
 * themes are first-class, not inverted. The neon accents are shared
 * across both themes.
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

        // Compatibility aliases used by feature pages. Keep these semantic so
        // they remain theme-aware instead of silently producing no CSS.
        background: "rgb(var(--bg) / <alpha-value>)",
        foreground: "rgb(var(--ink) / <alpha-value>)",
        border: "rgb(var(--line) / <alpha-value>)",
        "surface-2": "rgb(var(--surface) / <alpha-value>)",
        "surface-elevated": "rgb(var(--elevated) / <alpha-value>)",

        // Semantic neon accents. Blue leads interactions; yellow is reserved
        // for OPT, rewards, legendary rarity and hazard semantics.
        primary: {
          DEFAULT: "#168BFF",
          50: "#EAF4FF",
          100: "#CEE7FF",
          200: "#9DCEFF",
          300: "#66B1FF",
          400: "#3297FF",
          500: "#168BFF",
          600: "#0066D6",
          700: "#0751A6",
          800: "#0B417F",
          900: "#0D3567",
        },
        // `secondary` = AI/data/Web3 cyan.
        secondary: { DEFAULT: "#00E5FF", 500: "#00E5FF", 600: "#00A9C7" },
        mint: { DEFAULT: "#00E5FF", 500: "#00E5FF", 600: "#00A9C7" },
        reward: { DEFAULT: "#FCEE0A", 500: "#FCEE0A", 600: "#B7AB00" },
        // `tertiary` = hot magenta.
        tertiary: { DEFAULT: "#FF2E88", 500: "#FF2E88", 600: "#D11A6A" },
        magenta: { DEFAULT: "#FF2E88", 500: "#FF2E88", 600: "#D11A6A" },
        // `highlight` = hazard orange.
        highlight: { DEFAULT: "#FF6B2C", 500: "#FF6B2C", 600: "#D24E12" },
        amber: {
          DEFAULT: "#FFB020",
          400: "#FFB020",
          500: "#E89200",
          600: "#B86E00",
        },
        // `danger` = critical red (the classic CP2077 red).
        danger: { DEFAULT: "#FF003C", 500: "#FF003C" },
      },
      fontFamily: {
        display: ['"Chakra Petch"', '"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"Rajdhani"', '"Inter"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        "2xs": ["10px", { lineHeight: "1.3", letterSpacing: "0.04em" }],
        caption: ["11px", { lineHeight: "1.4", letterSpacing: "0.18em" }],
      },
      screens: {
        // Material Design 3 Window Size Classes (alongside standard Tailwind breakpoints).
        compact: { max: "599px" },
        medium: { min: "600px", max: "839px" },
        expanded: { min: "840px", max: "1199px" },
        large: { min: "1200px", max: "1599px" },
        xlarge: { min: "1600px" },
      },
      borderRadius: {
        // Cyberpunk leans angular: keep radii small and sharp.
        sm: "3px",
        card: "6px",
        hero: "10px",
      },
      boxShadow: {
        // Light day-cycle elevation.
        soft: "0 1px 0 rgba(0,0,0,.04), 0 18px 50px -30px rgba(0,0,0,.35)",
        // Dark elevation with a faint electric-blue glow.
        glowcard: "0 0 0 1px rgba(22,139,255,.12), 0 30px 80px -40px rgba(22,139,255,.34)",
        glow: "0 0 26px -4px rgba(22,139,255,.65)",
        glowmint: "0 0 26px -4px rgba(0,229,255,.6)",
        glowmagenta: "0 0 26px -4px rgba(255,46,136,.6)",
        glitch: "3px 0 0 rgba(255,0,60,.7), -3px 0 0 rgba(0,240,255,.7)",
      },
      backgroundImage: {
        "grad-signature": "linear-gradient(135deg, #168BFF 0%, #00E5FF 100%)",
        "grad-tertiary": "linear-gradient(135deg, #FF2E88 0%, #FF6B2C 100%)",
        "grad-cyan": "linear-gradient(135deg, #00E5FF 0%, #168BFF 100%)",
        "grad-border":
          "linear-gradient(135deg, rgba(22,139,255,.9), rgba(0,229,255,.85), rgba(255,46,136,.75))",
        scanlines:
          "repeating-linear-gradient(0deg, rgba(0,0,0,.28) 0px, rgba(0,0,0,.28) 1px, transparent 1px, transparent 3px)",
        hazard: "repeating-linear-gradient(45deg, #FCEE0A 0 14px, #0A0A0F 14px 28px)",
      },
      transitionTimingFunction: {
        smooth: "cubic-bezier(0.22, 1, 0.36, 1)",
        snap: "cubic-bezier(0.16, 1, 0.3, 1)",
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
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
        glitch: {
          "0%,92%,100%": { transform: "translate(0,0)" },
          "94%": { transform: "translate(-2px,1px)" },
          "96%": { transform: "translate(2px,-1px)" },
          "98%": { transform: "translate(-1px,-1px)" },
        },
        flicker: {
          "0%,100%": { opacity: "1" },
          "41%": { opacity: "1" },
          "42%": { opacity: "0.6" },
          "43%": { opacity: "1" },
          "92%": { opacity: "1" },
          "93%": { opacity: "0.7" },
          "94%": { opacity: "1" },
        },
        pulseNeon: {
          "0%,100%": { boxShadow: "0 0 0 0 rgba(22,139,255,.35)" },
          "50%": { boxShadow: "0 0 18px -2px rgba(22,139,255,.75)" },
        },
        floorScroll: {
          "0%": { backgroundPosition: "0 0" },
          "100%": { backgroundPosition: "0 46px" },
        },
        sheen: {
          "0%": { backgroundPosition: "200% 0" },
          "100%": { backgroundPosition: "-100% 0" },
        },
        sweep: {
          "0%": { top: "-40%" },
          "60%,100%": { top: "120%" },
        },
        blink: {
          "0%,49%": { opacity: "1" },
          "50%,100%": { opacity: "0.15" },
        },
      },
      animation: {
        aurora: "aurora 18s ease-in-out infinite",
        marquee: "marquee 40s linear infinite",
        shimmer: "shimmer 2.4s linear infinite",
        "spin-slow": "spinSlow 6s linear infinite",
        "rise-in": "riseIn .5s cubic-bezier(0.22,1,0.36,1) both",
        scan: "scan 5s linear infinite",
        glitch: "glitch 4s steps(1) infinite",
        flicker: "flicker 6s linear infinite",
        "pulse-neon": "pulseNeon 2.6s ease-in-out infinite",
        "floor-scroll": "floorScroll 3.6s linear infinite",
        sheen: "sheen 1.8s ease-in-out infinite",
        sweep: "sweep 4.6s ease-in-out infinite",
        blink: "blink 1.3s steps(1) infinite",
      },
    },
  },
} satisfies Config;
