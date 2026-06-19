import type { Config } from "tailwindcss";

// TODO(plan: Phase 4/5) — extend with the dark SRE theme palette.
const config: Config = {
  content: [
    "./src/app/**/*.{ts,tsx}",
    "./src/components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
};

export default config;
