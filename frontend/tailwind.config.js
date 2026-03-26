/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx,html,css}",
  ],
  theme: {
    extend: {
      colors: {
        "primary": "#00F0FF",
        "background-light": "#f5f8f8",
        "background-dark": "#09050E",
        "surface-base": "#140C20",
        "surface-glass": "rgba(28, 18, 45, 0.6)",
        "text-main": "#E2D9F3",
        "text-muted": "#8A7B9D",
        "danger": "#FF2E93",
        "success": "#00FF9D"
      },
      fontFamily: {
        "display": ["Space Grotesk", "sans-serif"],
        "body": ["Satoshi", "sans-serif"],
        "mono": ["JetBrains Mono", "monospace"]
      },
      boxShadow: {
        "glow-primary": "0 0 12px rgba(0, 240, 255, 0.2)",
        "glow-danger": "0 0 12px rgba(255, 46, 147, 0.4)",
        "glass": "0 8px 32px 0 rgba(0, 0, 0, 0.37)"
      }
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/container-queries')
  ],
}
