/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,jsx}'],
  theme: {
    extend: {
      boxShadow: {
        neon: '0 0 40px rgba(14, 165, 233, 0.25)',
      },
      colors: {
        ultra: '#0ea5e9',
        surface: '#0a1221',
      },
    },
  },
  plugins: [],
};
