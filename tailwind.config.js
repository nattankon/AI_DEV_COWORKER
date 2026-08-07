/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./frontend/**/*.{js,jsx}", "./styles/**/*.css"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Geist", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      colors: {
        panel: "#141518",
        panel2: "#191a1d",
        line: "#26282c",
        line2: "#33363b",
        ink: "#e6e7e9",
        muted: "#8a8d93",
        dim: "#5d6168",
        ok: "#3ddc97",
        warn: "#f5b14d",
        bad: "#ff5d5d",
        info: "#6aa8ff",
      },
      boxShadow: {
        panel: "0 1px 0 0 rgba(255,255,255,0.02) inset, 0 0 0 1px rgba(255,255,255,0.02)",
      },
    },
  },
  plugins: [],
};
