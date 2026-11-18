import type { Config } from "tailwindcss";
import animate from "tailwindcss-animate";

export default {
  darkMode: ["class"],
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(152 55% 96%)",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(40 45% 96%)",
        },
        info: {
          DEFAULT: "hsl(var(--info))",
          foreground: "hsl(210 60% 96%)",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        ai: "hsl(var(--ai))",
        ink: {
          DEFAULT: "hsl(var(--ink))",
          secondary: "hsl(var(--ink-secondary))",
        },
        brand: {
          DEFAULT: "#ED1B24",
          50: "#FEF2F2",
          100: "#FEE2E2",
          200: "#FECACA",
          300: "#FCA5A5",
          400: "#F87171",
          500: "#F04444",
          600: "#ED1B24",
          700: "#C8131B",
          800: "#A50F16",
          900: "#860E14",
          950: "#480509",
        },
        navy: {
          DEFAULT: "#283890",
          50: "#F0F1F8",
          100: "#DFE1F0",
          200: "#C0C5E2",
          300: "#969DCC",
          400: "#6C76B2",
          500: "#4C58A0",
          600: "#3A4590",
          700: "#283890",
          800: "#232E77",
          900: "#1E2763",
          950: "#121738",
        },
        sand: {
          DEFAULT: "#F7F7F7",
          50: "#FCFCFC",
          100: "#F7F7F7",
          200: "#EFEFEF",
          300: "#E4E4E4",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      boxShadow: {
        card: "var(--shadow-card)",
        lift: "var(--shadow-lift)",
        "inset-line": "var(--shadow-inset-line)",
      },
      fontFamily: {
        sans: [
          "Outfit",
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
        ],
        display: [
          "Playfair Display",
          "Georgia",
          "ui-serif",
          "serif",
        ],
        mono: ["ui-monospace", "SFMono-Regular", "Menlo", "Consolas", "monospace"],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "none" },
        },
        "fade-in-up": {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "none" },
        },
        shimmer: {
          from: { backgroundPosition: "200% 0" },
          to: { backgroundPosition: "-200% 0" },
        },
        "pulse-soft": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.45" },
        },
        sweep: {
          from: { transform: "translateX(-100%)" },
          to: { transform: "translateX(250%)" },
        },
        "progress-indeterminate": {
          "0%": { transform: "translateX(-100%)" },
          "100%": { transform: "translateX(200%)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        "fade-in": "fade-in 0.25s ease-out",
        "fade-in-up": "fade-in-up 0.4s cubic-bezier(0.16, 1, 0.3, 1)",
        shimmer: "shimmer 2.2s linear infinite",
        "pulse-soft": "pulse-soft 1.8s ease-in-out infinite",
        sweep: "sweep 1.6s ease-in-out infinite",
        "progress-indeterminate": "progress-indeterminate 1.2s ease-in-out infinite",
      },
    },
  },
  plugins: [animate],
} satisfies Config;