/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // ── Surface ladder (crisp clinical light palette) ──
        obsidian: '#f8fafc',
        carbon: '#ffffff',
        graphite: '#f1f5f9',
        slate2: '#eff6ff',
        ridge: '#cbd5e1',
        // ── Text ──
        ink: {
          DEFAULT: '#0f172a',
          soft: '#1e293b',
          mute: '#475569',
          faint: '#64748b',
        },
        // ── Semantic clinical accents (high-contrast for printing) ──
        clinical: {
          cyan: '#0891b2',
          cyanSoft: '#06b6d4',
          emerald: '#059669',
          amber: '#d97706',
          rose: '#e11d48',
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
        specular: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
        float: '0 20px 25px -5px rgba(0, 0, 0, 0.08), 0 8px 10px -6px rgba(0, 0, 0, 0.04), 0 0 0 1px #cbd5e1',
        glow: '0 0 0 1px rgba(8, 145, 178, 0.35), 0 8px 24px -8px rgba(8, 145, 178, 0.25)',
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
