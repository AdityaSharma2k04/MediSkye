/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ── Surface ladder (darkest → raised) ──
        obsidian: '#05070b',
        carbon: '#0a0e17',
        graphite: '#0f1623',
        slate2: '#151d2c',
        ridge: '#1c2638',
        // ── Text ──
        ink: {
          DEFAULT: '#e6edf5',
          soft: '#c3cedb',
          mute: '#8a97a8',
          faint: '#5d6a7c',
        },
        // ── Semantic clinical accents ──
        clinical: {
          cyan: '#06b6d4',
          cyanSoft: '#67e8f9',
          emerald: '#10b981',
          amber: '#f59e0b',
          rose: '#f43f5e',
        },
        brand: {
          50: '#f8fafc',
          100: '#f1f5f9',
          500: '#64748b',
          600: '#475569',
          700: '#334155',
          800: '#1e293b',
          900: '#0f172a',
        },
      },
      fontFamily: {
        sans: ['"Inter Variable"', 'Inter', '-apple-system', 'BlinkMacSystemFont', '"Segoe UI Variable Text"', '"Segoe UI"', 'sans-serif'],
        display: ['"Fraunces Variable"', 'Fraunces', 'Georgia', 'serif'],
        mono: ['"JetBrains Mono Variable"', '"JetBrains Mono"', 'ui-monospace', '"Cascadia Mono"', 'Consolas', 'monospace'],
      },
      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },
      borderRadius: {
        xl: '12px',
        '2xl': '16px',
        '3xl': '24px',
      },
      boxShadow: {
        specular: 'inset 0 1px 0 0 rgba(255,255,255,0.05)',
        float: '0 24px 64px -16px rgba(0,0,0,0.7), 0 0 0 1px rgba(255,255,255,0.06)',
        glow: '0 0 0 1px rgba(6,182,212,0.35), 0 8px 32px -8px rgba(6,182,212,0.35)',
      },
      transitionTimingFunction: {
        out: 'cubic-bezier(0.22, 1, 0.36, 1)',
      },
      keyframes: {
        'token-pulse': {
          '0%, 100%': { opacity: '0.25' },
          '50%': { opacity: '1' },
        },
        'stage-sweep': {
          '0%': { transform: 'translateX(-100%)' },
          '100%': { transform: 'translateX(100%)' },
        },
      },
      animation: {
        'token-pulse': 'token-pulse 1.1s ease-in-out infinite',
        'stage-sweep': 'stage-sweep 1.6s cubic-bezier(0.4, 0, 0.2, 1) infinite',
      },
    },
  },
  plugins: [require('@tailwindcss/typography')],
};
