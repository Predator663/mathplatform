/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        display: ['"Syne"', 'sans-serif'],
        body: ['"DM Sans"', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      colors: {
        ink: {
          950: '#0a0a0f', 900: '#111118', 800: '#1a1a26',
          700: '#242433', 600: '#2e2e42', 500: '#3d3d55',
        },
        azure:   { 400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb' },
        emerald: { 400: '#34d399', 500: '#10b981' },
        amber:   { 400: '#fbbf24', 500: '#f59e0b' },
        rose:    { 400: '#fb7185', 500: '#f43f5e' },
        violet:  { 400: '#a78bfa', 500: '#8b5cf6' },
      },
      backgroundImage: {
        'grid-ink': 'linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px)',
      },
      backgroundSize: { grid: '40px 40px' },
      boxShadow: {
        'glow-blue':  '0 0 20px rgba(59,130,246,0.25)',
        'glow-green': '0 0 20px rgba(16,185,129,0.25)',
        'glow-amber': '0 0 20px rgba(245,158,11,0.25)',
      },
      keyframes: {
        slideInLeft: {
          from: { transform: 'translateX(-100%)' },
          to:   { transform: 'translateX(0)' },
        },
      },
      animation: {
        'slideInLeft': 'slideInLeft 0.2s ease-out',
      },
    },
  },
  plugins: [
    function({ addUtilities }) {
      addUtilities({
        '.no-scrollbar': {
          '-ms-overflow-style': 'none',
          'scrollbar-width': 'none',
          '&::-webkit-scrollbar': { display: 'none' },
        },
      });
    },
  ],
}
