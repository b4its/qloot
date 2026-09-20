import type { Config } from "tailwindcss";

/**
 * QLoot design system — retro-cyberpunk / "Night City" 2077 aesthetic.
 *
 * Near-black carbon surfaces with neon accents (acid yellow, ICE cyan,
 * hot magenta and hazard orange). Colors are driven by CSS variables
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

        // Neon accents (same in both themes).
        // `primary` = Acid yellow (Night City signature).
        primary: {
          DEFAULT: "#FCEE0A",
          50: "#FEFCE0",
          100: "#FDF9B8",
          200: "#FCF470",
          300: "#FCEF2E",
          400: "#FCEE0A",
          500: "#E8D900",
          600: "#B7AB00",
          700: "#867D00",
          800: "#545000",
          900: "#2B2900",
        },
        // `secondary` = ICE cyan.
        secondary: { DEFAULT: "#00F0FF", 500: "#00F0FF", 600: "#00B8C4" },
        // `tertiary` = hot magenta.
        tertiary: { DEFAULT: "#FF2E88", 500: "#FF2E88", 600: "#D11A6A" },
        // `highlight` = hazard orange.
        highlight: { DEFAULT: "#FF6B2C", 500: "#FF6B2C", 600: "#D24E12" },
        // `danger` = critical red (the classic CP2077 red).
        danger: { DEFAULT: "#FF003C", 500: "#FF003C" },
      },
      fontFamily: {
        display: ['"Chakra Petch"', '"Space Grotesk"', "system-ui", "sans-serif"],
        sans: ['"Rajdhani"', '"Inter"', "system-ui", "-apple-system", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      fontSize: {
        caption: ["11px", { lineHeight: "1.4", letterSpacing: "0.18em" }],
      },
      borderRadius: {
        // Cyberpunk leans angular: keep radii small and sharp.
        sm: "3px",
        card: "6px",
        hero: "10px",
      },
      boxShadow: {
        // Light "day cycle" elevation.
        soft: "0 1px 0 rgba(0,0,0,.04), 0 18px 50px -30px rgba(0,0,0,.35)",
        // Dark elevation with a faint acid-yellow glow.
        glowcard: "0 0 0 1px rgba(252,238,10,.10), 0 30px 80px -40px rgba(252,238,10,.28)",
        glow: "0 0 26px -4px rgba(252,238,10,.65)",
        glowmint: "0 0 26px -4px rgba(0,240,255,.6)",
        glowmagenta: "0 0 26px -4px rgba(255,46,136,.6)",
        glitch: "3px 0 0 rgba(255,0,60,.7), -3px 0 0 rgba(0,240,255,.7)",
      },
      backgroundImage: {
        "grad-signature": "linear-gradient(135deg, #FCEE0A 0%, #FF6B2C 100%)",
        "grad-tertiary": "linear-gradient(135deg, #FF2E88 0%, #FF6B2C 100%)",
        "grad-cyan": "linear-gradient(135deg, #00F0FF 0%, #FCEE0A 100%)",
        "grad-border":
          "linear-gradient(135deg, rgba(252,238,10,.9), rgba(0,240,255,.85), rgba(255,46,136,.8))",
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
          "0%,100%": { boxShadow: "0 0 0 0 rgba(252,238,10,.35)" },
          "50%": { boxShadow: "0 0 18px -2px rgba(252,238,10,.75)" },
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
