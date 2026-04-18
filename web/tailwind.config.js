/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: '#007acc',
          dark: '#005a9e',
          light: '#3794ff',
        },
        surface: {
          DEFAULT: '#252526',
          light: '#2d2d2e',
          dark: '#1e1e1e',
        },
        success: '#4CAF50',
        warning: '#ff9800',
        error: '#f44336',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
