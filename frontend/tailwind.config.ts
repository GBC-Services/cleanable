import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{ts,tsx,mdx}"],
  darkMode: ["class"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#E8F5F5",
          100: "#D1EBEB",
          200: "#A3D7D7",
          300: "#74C3C3",
          400: "#46AFAF",
          500: "#01696F", // primary — Cleanable teal
          600: "#015459",
          700: "#013F43",
          800: "#002A2D",
          900: "#001517",
        },
        surface: {
          DEFAULT: "#F7F6F2",
          card: "#FFFFFF",
          muted: "#F2F1ED",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};

export default config;
