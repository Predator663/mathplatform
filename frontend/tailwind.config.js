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
          950: 'var(--bg-950)', 900: 'var(--bg-900)', 800: 'var(--bg-800)',
          700: 'var(--bg-700)', 600: 'var(--bg-600)', 500: 'var(--bg-500)',
          400: 'var(--text-muted)',
        },
        azure:   { 300: '#93c5fd', 400: '#60a5fa', 500: '#3b82f6', 600: '#2563eb', 700: '#1d4ed8' },
        emerald: { 400: '#34d399', 500: '#10b981' },
        amber:   { 400: '#fbbf24', 500: '#f59e0b' },
        rose:    { 300: '#fda4af', 400: '#fb7185', 500: '#f43f5e', 600: '#e11d48' },
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
