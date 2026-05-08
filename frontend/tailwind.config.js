/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{vue,js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        ivory: {
          DEFAULT: "#FFFFF0",
          light: "#FEFEF8",
          dark: "#F5F5DC",
        },
        "page-mist": "#f9f7fc",
        "matte-lilac": "#e8e2f2",
        "matte-sage": "#dde8e0",
        "matte-blue": "#dbe4f0",
        "matte-dust": "#ebe6f4",
        "pastel-lavender": "#E6E6FA",
        "pastel-mint": "#B2DFDB",
        "pastel-peach": "#FFDAB9",
        "pastel-blue": "#BBDEFB",
        "pastel-rose": "#F8BBD0",
        charcoal: "#2D2D2D",
      },
      boxShadow: {
        soft: "0 8px 20px rgba(45, 45, 45, 0.08)",
      },
    },
  },
  plugins: [],
};
