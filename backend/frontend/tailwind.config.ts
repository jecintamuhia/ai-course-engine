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
        burgundy: {
          DEFAULT: "#6B1F32",
          50: "#FBF2F5",
          100: "#F5E0E6",
          200: "#E9BDCA",
          300: "#D891A3",
          400: "#C26479",
          500: "#A3495E",
          600: "#833448",
          700: "#6B1F32",
          800: "#42131F",
          900: "#35101A",
          950: "#260A12",
        },
        cream: {
          DEFAULT: "#F8F3EA",
          50: "#FFFDF9",
          100: "#F8F3EA",
          200: "#EEE6DA",
          300: "#E4DCD2",
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
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "Roboto",
          "sans-serif",
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