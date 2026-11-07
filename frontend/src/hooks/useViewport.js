import { useEffect, useState } from 'react';

export const BREAKPOINTS = { md: 768, lg: 1024, xl: 1280 };

function read() {
  if (typeof window === 'undefined') return { width: BREAKPOINTS.lg, height: 800 };
  return { width: window.innerWidth, height: window.innerHeight };
}

/**
 * Viewport size + semantic flags.
 * Uses `innerWidth` (not matchMedia) so behaviour is deterministic in JSDOM
 * tests that set `window.innerWidth` directly.
 *
 *  isDesktop  ≥ 1024px  → split-pane clinical workbench
 *  isTablet   768–1023  → single pane, side drawer navigation
 *  isMobile   < 768px   → top bar + bottom sheets
 */
export default function useViewport() {
  const [size, setSize] = useState(read);

  useEffect(() => {
    let frame = null;
    const onResize = () => {
      if (frame) cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => setSize(read()));
    };
    window.addEventListener('resize', onResize);
    window.addEventListener('orientationchange', onResize);
    return () => {
      if (frame) cancelAnimationFrame(frame);
      window.removeEventListener('resize', onResize);
      window.removeEventListener('orientationchange', onResize);
    };
  }, []);

  return {
    ...size,
    isDesktop: size.width >= BREAKPOINTS.lg,
    isTablet: size.width >= BREAKPOINTS.md && size.width < BREAKPOINTS.lg,
    isMobile: size.width < BREAKPOINTS.md,
  };
}
