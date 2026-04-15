import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./src/**/*.{js,ts,jsx,tsx,mdx}"],
  theme: {
    extend: {
      colors: {
        nadir: {
          bg: "#0a0e17",
          surface: "#111827",
          border: "#1f2937",
          accent: "#3b82f6",
          critical: "#ef4444",
          warning: "#f59e0b",
          success: "#10b981",
          muted: "#6b7280",
        },
      },
      fontFamily: {
        mono: ["JetBrains Mono", "Fira Code", "monospace"],
      },
    },
  },
  plugins: [],
};
export default config;
