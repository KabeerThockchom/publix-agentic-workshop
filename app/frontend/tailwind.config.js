/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        publix: {
          green: '#4c8c2b',
          dark: '#3a6d21',
          light: '#eaf3e3',
        },
        navy: '#0B2026',
        lava: '#FF3621',
        surface: '#F9F7F4',
      },
      fontFamily: {
        sans: ['"DM Sans"', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
