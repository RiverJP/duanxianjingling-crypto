import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        panel: "#f7f7f2",
        mint: "#2a9d8f",
        coral: "#e76f51",
        gold: "#e9c46a"
      }
    }
  },
  plugins: []
};

export default config;
