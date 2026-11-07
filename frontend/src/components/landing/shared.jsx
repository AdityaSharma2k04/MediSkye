import React from 'react';

/* ─── Palette (mirrors tailwind.config: obsidian + medical) ─── */
export const C = {
  obsidian: '#05070b',
  obsidianLight: '#0f1623',
  panel: '#0a0e17',
  border: 'rgba(255,255,255,0.08)',
  borderStrong: 'rgba(255,255,255,0.16)',
  cyan: '#06b6d4', // medical.cyan
  cyanDark: '#0891b2', // medical.dark
  cyanText: '#22d3ee', // cyan tint for text on dark (AA contrast)
  heading: '#ffffff',
  body: '#c3cedb',
  muted: '#8a97a8',
  amber: '#fbbf24',
  green: '#34d399',
  red: '#f87171',
};

export const SERIF = "'Fraunces Variable', Fraunces, Georgia, serif";
export const SANS = "'Inter Variable', Inter, system-ui, -apple-system, 'Segoe UI', sans-serif";

// Auto-fit grid that never overflows narrow phones
export const fit = (min) => `repeat(auto-fit, minmax(min(100%, ${min}px), 1fr))`;

/* ─── Icons (inline SVGs, zero external icon dependencies) ─── */
export const Icon = ({ size = 24, strokeWidth = 1.5, children }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth={strokeWidth}
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
  >
    {children}
  </svg>
);

export const ActivityIcon = (p) => (
  <Icon strokeWidth={2} {...p}>
    <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
  </Icon>
);

export const FlaskIcon = (p) => (
  <Icon {...p}>
    <path d="M9 3h6" />
    <path d="M10 9V3" />
    <path d="M14 9V3" />
    <path d="M6 21h12" />
    <path d="M10 9l-4 8c-.7 1.3.13 3 1.76 3h8.48c1.63 0 2.46-1.7 1.76-3L14 9" />
  </Icon>
);

export const BrainIcon = (p) => (
  <Icon {...p}>
    <path d="M9.5 2A5.5 5.5 0 0 0 4 7.5c0 1.28.44 2.46 1.18 3.39" />
    <path d="M14.5 2A5.5 5.5 0 0 1 20 7.5c0 1.28-.44 2.46-1.18 3.39" />
    <path d="M5.18 10.89A5.5 5.5 0 0 0 4 14.5 5.5 5.5 0 0 0 9.5 20h1" />
    <path d="M18.82 10.89A5.5 5.5 0 0 1 20 14.5a5.5 5.5 0 0 1-5.5 5.5h-1" />
    <path d="M12 2v20" />
  </Icon>
);

export const ScanIcon = (p) => (
  <Icon {...p}>
    <path d="M3 7V5a2 2 0 0 1 2-2h2" />
    <path d="M17 3h2a2 2 0 0 1 2 2v2" />
    <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
    <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
    <line x1="7" y1="12" x2="17" y2="12" />
  </Icon>
);

export const UploadIcon = (p) => (
  <Icon {...p}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </Icon>
);

export const SparklesIcon = (p) => (
  <Icon {...p}>
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
  </Icon>
);

export const SendIcon = (p) => (
  <Icon strokeWidth={2} {...p}>
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </Icon>
);

export const sharedStyles = {
  eyebrow: {
    fontSize: 14,
    fontWeight: 500,
    color: C.cyanText,
    margin: '0 0 14px',
  },
  sectionTitle: {
    fontFamily: SERIF,
    fontSize: 'clamp(30px, 3.6vw, 44px)',
    fontWeight: 450,
    letterSpacing: '-0.02em',
    lineHeight: 1.1,
    color: C.heading,
    margin: '0 0 16px',
  },
  sectionSubtitle: {
    fontSize: 17,
    lineHeight: 1.65,
    color: C.muted,
    margin: 0,
  },
  btnPrimary: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    padding: '0 24px',
    borderRadius: 12,
    background: C.cyan,
    color: C.obsidian,
    fontSize: 15,
    fontWeight: 600,
    textDecoration: 'none',
  },
  logoBox: {
    width: 32,
    height: 32,
    borderRadius: 9,
    background: 'linear-gradient(150deg, #0e7490 0%, #06b6d4 70%)',
    color: '#031016',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
};
