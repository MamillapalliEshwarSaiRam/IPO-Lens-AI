import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
    "./lib/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        ink: "#18181b",
        paper: "#f7f5f0",
        graphite: "#3f3f46",
        signal: "#2563eb",
        mint: "#059669",
        caution: "#d97706",
        danger: "#dc2626",
        ember: "#ea580c"
      },
      boxShadow: {
        panel: "0 16px 40px rgba(24, 24, 27, 0.08)"
      }
    }
  },
  plugins: []
};

export default config;

