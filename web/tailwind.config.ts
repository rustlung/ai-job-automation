import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ink: "#202124",
        canvas: "#f7f8fa",
        line: "#e2e5e9",
        success: "#18794e",
        warning: "#b54708",
        danger: "#b42318"
      }
    }
  },
  plugins: []
} satisfies Config;
