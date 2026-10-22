import React, { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Trans, useTranslation } from 'react-i18next';
import useIntersectionObserver from '../hooks/useIntersectionObserver';
import {
  C,
  SERIF,
  SANS,
  fit,
  ActivityIcon,
  SparklesIcon,
  SendIcon,
} from './landing/shared';
function createLazySection(importFn) {
  let cached = null;
  let promise = null;

  const load = () => {
    if (!promise) {
      promise = importFn().then((mod) => {
        cached = mod;
        return mod;
      });
    }
    return promise;
  };

  if (import.meta.env.MODE === 'test') {
    load();
  }

  const LazyComp = lazy(() => {
    if (cached) {
      return {
        then(onFulfilled) {
          onFulfilled(cached);
          return this;
        },
      };
    }
    return load();
  });

  LazyComp.preload = load;
  return LazyComp;
}

const FeaturesSection = createLazySection(() => import('./landing/FeaturesSection'));
const HowItWorksSection = createLazySection(() => import('./landing/HowItWorksSection'));
const SafetySection = createLazySection(() => import('./landing/SafetySection'));
const CTASection = createLazySection(() => import('./landing/CTASection'));
const FooterSection = createLazySection(() => import('./landing/FooterSection'));

if (import.meta.env.MODE === 'test') {
  await Promise.all([
    FeaturesSection.preload(),
    HowItWorksSection.preload(),
    SafetySection.preload(),
    CTASection.preload(),
    FooterSection.preload(),
  ]);
}

export default function LandingPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const heroRef = useRef(null);
  const [activeSection, setActiveSection] = useState('');
  const [forcedSections, setForcedSections] = useState({});

  const handleNavClick = async (e, sectionId) => {
    if (e && typeof e.preventDefault === 'function') {
      e.preventDefault();
    }
    setActiveSection(sectionId);

    // Preload chunk modules so that Suspense won't need to show a fallback
    try {
      if (sectionId === 'features') {
        await FeaturesSection.preload?.();
      } else if (sectionId === 'how-it-works') {
        await Promise.all([
          FeaturesSection.preload?.(),
          HowItWorksSection.preload?.(),
        ]);
      } else if (sectionId === 'safety') {
        await Promise.all([
          FeaturesSection.preload?.(),
          HowItWorksSection.preload?.(),
          SafetySection.preload?.(),
        ]);
      }
    } catch (_) {}

    // Force section(s) to render
    setForcedSections((prev) => {
      if (sectionId === 'how-it-works') {
        return { ...prev, features: true, 'how-it-works': true };
      }
      if (sectionId === 'safety') {
        return { ...prev, features: true, 'how-it-works': true, safety: true };
      }
      return { ...prev, [sectionId]: true };
    });

    // Wait a tick for React to commit DOM and layout to stabilize
    requestAnimationFrame(() => {
      setTimeout(() => {
        const element = document.getElementById(sectionId);
        if (element) {
          // Target the heading inside the section so the viewport lands just a bit above it
          const heading = element.querySelector('h2') || element;
          const headingTop = heading.getBoundingClientRect().top + window.pageYOffset;
          const targetY = Math.max(0, headingTop - 116);
          window.scrollTo({
            top: targetY,
            behavior: 'smooth',
          });
        }
      }, 50);
    });
  };

  // Scroll-spy to highlight active nav link as user scrolls
  useEffect(() => {
    const handleScroll = () => {
      const scrollY = window.scrollY || window.pageYOffset;
      if (scrollY < 180) {
        setActiveSection('');
        return;
      }

      const sectionIds = ['features', 'how-it-works', 'safety'];
      const triggerOffset = 140;

      let current = '';
      for (const id of sectionIds) {
        const el = document.getElementById(id);
        if (el) {
          const rect = el.getBoundingClientRect();
          if (rect.top <= triggerOffset) {
            current = id;
          }
        }
      }
      setActiveSection(current);
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  // If already authenticated, redirect to /chat
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const base64Url = token.split('.')[1];
        if (base64Url) {
          const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
          const payload = JSON.parse(atob(base64));
          if (payload.exp && payload.exp * 1000 > Date.now()) {
            navigate('/chat', { replace: true });
            return;
          }
        }
      } catch (_) {
        // invalid token, stay on landing
      }
    }
  }, [navigate]);

  // Apply dark mode & page title
  useEffect(() => {
    document.documentElement.classList.add('dark');
    document.title = 'MediSkye — Understand Your Medical Reports in Seconds';
  }, []);

  // Prefetch below-the-fold chunks on idle so they are cached before user scrolls
  useEffect(() => {
    const prefetch = () => {
      import('./landing/FeaturesSection');
      import('./landing/HowItWorksSection');
      import('./landing/SafetySection');
      import('./landing/CTASection');
      import('./landing/FooterSection');
    };
    if (typeof window !== 'undefined') {
      if ('requestIdleCallback' in window) {
        requestIdleCallback(prefetch);
      } else {
        setTimeout(prefetch, 2000);
      }
    }
  }, []);

  return (
    <div style={styles.page} className="landing bg-zinc-950 text-zinc-50">
      {/* ━━━━━━━━━━ NAVBAR ━━━━━━━━━━ */}
      <nav style={styles.nav} id="landing-nav" aria-label="Main Navigation">
        <div style={styles.navInner}>
          <Link to="/" style={styles.navBrand} aria-label="MediSkye Home">
            <div style={styles.logoBox}>
              <ActivityIcon size={18} />
            </div>
            <span style={styles.navLogoText}>MediSkye</span>
          </Link>

          <div style={styles.navLinks} className="landing-nav-links">
            <a
              href="#features"
              onClick={(e) => handleNavClick(e, 'features')}
              style={{
                ...styles.navLink,
                ...(activeSection === 'features' ? styles.navLinkActive : {}),
              }}
              className={`landing-link ${activeSection === 'features' ? 'landing-link-active' : ''}`}
              aria-current={activeSection === 'features' ? 'page' : undefined}
            >
              {t('landing.nav_features', 'Features')}
            </a>
            <a
              href="#how-it-works"
              onClick={(e) => handleNavClick(e, 'how-it-works')}
              style={{
                ...styles.navLink,
                ...(activeSection === 'how-it-works' ? styles.navLinkActive : {}),
              }}
              className={`landing-link ${activeSection === 'how-it-works' ? 'landing-link-active' : ''}`}
              aria-current={activeSection === 'how-it-works' ? 'page' : undefined}
            >
              {t('landing.nav_how_it_works', 'How it works')}
            </a>
            <a
              href="#safety"
              onClick={(e) => handleNavClick(e, 'safety')}
              style={{
                ...styles.navLink,
                ...(activeSection === 'safety' ? styles.navLinkActive : {}),
              }}
              className={`landing-link ${activeSection === 'safety' ? 'landing-link-active' : ''}`}
              aria-current={activeSection === 'safety' ? 'page' : undefined}
            >
              {t('landing.nav_safety', 'Safety')}
            </a>
          </div>

          <div style={styles.navActions}>
            <Link
              to="/login"
              style={styles.navBtnGhost}
              className="landing-link"
              id="landing-login-btn"
            >
              {t('landing.nav_sign_in', 'Sign in')}
            </Link>
            <Link
              to="/register"
              style={styles.btnPrimary}
              className="landing-btn-primary"
              id="landing-register-btn"
            >
              {t('landing.nav_get_started', 'Get started')}
            </Link>
          </div>
        </div>
      </nav>

      {/* ━━━━━━━━━━ HERO ━━━━━━━━━━ */}
      <section style={styles.hero} ref={heroRef} id="hero">
        <div style={styles.heroContent}>
          <div style={styles.heroBadge}>
            <SparklesIcon size={14} />
            <span>{t('landing.hero_badge', 'Clinical AI Interpretation')}</span>
          </div>

          <h1 style={styles.heroTitle}>
            <Trans
              i18nKey="landing.hero_title_accent"
              defaults="Understand your medical reports <accent>in seconds.</accent>"
              components={{ accent: <em style={styles.heroTitleAccent} /> }}
            />
          </h1>

          <p style={styles.heroSubtitle}>
            {t(
              'landing.hero_subtitle',
              'Upload any lab report or medical document. MediSkye reads it, extracts the key metrics, and explains everything in plain language, so you walk into every doctor visit fully informed.'
            )}
          </p>

          <div style={styles.heroButtons}>
            <Link
              to="/register"
              style={styles.btnPrimary}
              className="landing-btn-primary"
              id="hero-cta-primary"
            >
              {t('landing.start_free', 'Start for free')}
            </Link>
            <a
              href="#how-it-works"
              onClick={(e) => handleNavClick(e, 'how-it-works')}
              style={styles.btnSecondary}
              className="landing-btn-secondary"
            >
              {t('landing.see_how_it_works', 'See how it works')}
            </a>
          </div>
        </div>

        <ChatMockup />
      </section>

      {/* ━━━━━━━━━━ FEATURES ━━━━━━━━━━ */}
      <DeferredSection
        id="features"
        minHeight={560}
        className="scroll-mt-24 md:scroll-mt-32"
        forceVisible={Boolean(forcedSections['features'])}
      >
        <Suspense fallback={<div style={{ minHeight: 560 }} aria-hidden="true" />}>
          <FeaturesSection />
        </Suspense>
      </DeferredSection>

      {/* ━━━━━━━━━━ HOW IT WORKS ━━━━━━━━━━ */}
      <DeferredSection
        id="how-it-works"
        minHeight={780}
        className="scroll-mt-24 md:scroll-mt-32"
        forceVisible={Boolean(forcedSections['how-it-works'])}
      >
        <Suspense fallback={<div style={{ minHeight: 780 }} aria-hidden="true" />}>
          <HowItWorksSection />
        </Suspense>
      </DeferredSection>

      {/* ━━━━━━━━━━ SAFETY ━━━━━━━━━━ */}
      <DeferredSection
        id="safety"
        minHeight={620}
        className="scroll-mt-24 md:scroll-mt-32"
        forceVisible={Boolean(forcedSections['safety'])}
      >
        <Suspense fallback={<div style={{ minHeight: 620 }} aria-hidden="true" />}>
          <SafetySection />
        </Suspense>
      </DeferredSection>

      {/* ━━━━━━━━━━ CTA ━━━━━━━━━━ */}
      <DeferredSection minHeight={440}>
        <Suspense fallback={<div style={{ minHeight: 440 }} aria-hidden="true" />}>
          <CTASection />
        </Suspense>
      </DeferredSection>

      {/* ━━━━━━━━━━ FOOTER ━━━━━━━━━━ */}
      <DeferredSection id="landing-footer" minHeight={400}>
        <Suspense fallback={<div style={{ minHeight: 400 }} aria-hidden="true" />}>
          <FooterSection />
        </Suspense>
      </DeferredSection>

      {/* Inline CSS: fonts, keyframes, hover/focus, responsive */}
      <style>{css}</style>
    </div>
  );
}

function DeferredSection({ children, id, minHeight, className = '', forceVisible = false }) {
  const [ref, isVisible] = useIntersectionObserver({ rootMargin: '500px 0px' });
  const shouldRender = isVisible || forceVisible;

  return (
    <div
      ref={ref}
      id={id}
      style={{
        ...(shouldRender ? {} : { minHeight }),
        scrollMarginTop: '110px',
      }}
      className={className}
      aria-busy={!shouldRender}
      aria-hidden={!shouldRender}
    >
      {shouldRender ? children : null}
    </div>
  );
}

/* ─── Hero chat mockup (mirrors the real app UI) ─── */
function ChatMockup() {
  return (
    <div style={styles.mockupWrapper}>
      <div style={styles.mockupCard} className="landing-mockup">
        <div style={styles.mockupHeader}>
          <div style={styles.mockupDots}>
            <span style={{ ...styles.mockupDot, background: '#ef4444' }} />
            <span style={{ ...styles.mockupDot, background: '#f59e0b' }} />
            <span style={{ ...styles.mockupDot, background: '#22c55e' }} />
          </div>
          <span style={styles.mockupHeaderTitle}>MediSkye AI Chat</span>
          <div style={{ width: 46 }} />
        </div>

        <div style={styles.mockupBody}>
          {/* User message */}
          <div style={styles.msgUserRow}>
            <div style={styles.bubbleUser}>
              What does my Hemoglobin level mean? The report says 11.2 g/dL.
            </div>
          </div>

          {/* AI response */}
          <div style={styles.msgAiRow}>
            <div style={styles.aiAvatar}>
              <ActivityIcon size={14} />
            </div>
            <div style={styles.bubbleAi}>
              <div style={styles.aiLabel}>MediSkye AI</div>
              <div>
                Your Hemoglobin is <strong style={{ color: C.amber }}>11.2 g/dL</strong>, which is
                slightly below the normal range (12.0–16.0 g/dL for women). This may indicate mild{' '}
                <strong style={{ color: C.heading }}>anemia</strong>. Common causes include iron
                deficiency, vitamin B12 deficiency, or chronic conditions.
              </div>
              <div style={styles.metricChip}>
                <span style={styles.chipDot} />
                Hemoglobin: 11.2 g/dL — Borderline Low
              </div>
            </div>
          </div>

          {/* Typing indicator */}
          <div style={{ ...styles.msgAiRow, alignItems: 'center' }}>
            <div style={styles.aiAvatar}>
              <ActivityIcon size={14} />
            </div>
            <div style={styles.typing} aria-hidden="true">
              <span style={styles.typingDot(0)} />
              <span style={styles.typingDot(0.2)} />
              <span style={styles.typingDot(0.4)} />
            </div>
          </div>
        </div>

        {/* Decorative input bar */}
        <div style={styles.mockupInputBar} aria-hidden="true">
          <div style={styles.mockupInput}>Ask about your report...</div>
          <div style={styles.mockupSendBtn}>
            <SendIcon size={16} />
          </div>
        </div>
      </div>
    </div>
  );
}

/* ─── CSS: fonts, keyframes, hover/focus, responsive ─── */
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,500;1,6..72,500&display=swap');

  html { scroll-padding-top: 96px; }

  @keyframes landing-float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
  }
  @keyframes landing-typing {
    0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
    40% { opacity: 1; transform: scale(1); }
  }
  @keyframes landing-fade-up {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  /* Fade-in on scroll */
  .fade-in-section {
    opacity: 0;
    transform: translateY(20px);
    transition: opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    will-change: opacity, transform;
  }
  .fade-in-section.is-visible {
    opacity: 1;
    transform: translateY(0);
  }

  img {
    content-visibility: auto;
  }

  .landing-mockup { animation: landing-float 6s ease-in-out infinite; }

  .landing-link:hover { color: #fafafa !important; }
  .landing-link-active {
    color: #ffffff !important;
    border-bottom: 2px solid #06b6d4 !important;
    font-weight: 600 !important;
  }
  .landing-btn-primary { transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease; }
  .landing-btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(6, 182, 212, 0.28);
  }
  .landing-btn-secondary { transition: border-color 0.15s ease, color 0.15s ease, background-color 0.15s ease; }
  .landing-btn-secondary:hover { border-color: #52525b !important; color: #fafafa !important; background-color: rgba(255, 255, 255, 0.03); }



  .landing a:focus-visible {
    outline: 2px solid #22d3ee;
    outline-offset: 3px;
    border-radius: 6px;
  }

  @media (max-width: 760px) {
    .landing-nav-links { display: none !important; }
  }

  @media (prefers-reduced-motion: reduce) {
    .landing *, .landing *::before, .landing *::after {
      animation: none !important;
      transition: none !important;
    }
    html { scroll-behavior: auto; }
  }
`;

/* ─── Styles (inline object) ─── */
const styles = {
  // ── Page ──
  page: {
    minHeight: '100vh',
    background: C.obsidian,
    color: '#fafafa',
    fontFamily: SANS,
    lineHeight: 1.6,
    overflowX: 'clip',
  },

  // ── Shared ──
  eyebrow: {
    fontSize: 13,
    fontWeight: 600,
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    color: C.cyanText,
    margin: '0 0 16px',
  },
  sectionTitle: {
    fontFamily: SERIF,
    fontSize: 'clamp(30px, 3.6vw, 44px)',
    fontWeight: 500,
    letterSpacing: '-0.01em',
    lineHeight: 1.15,
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
  btnSecondary: {
    display: 'inline-flex',
    alignItems: 'center',
    justifyContent: 'center',
    minHeight: 46,
    padding: '0 22px',
    borderRadius: 12,
    border: `1px solid ${C.borderStrong}`,
    color: '#e4e4e7',
    fontSize: 15,
    fontWeight: 500,
    textDecoration: 'none',
  },
  logoBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: '#fafafa',
    color: C.obsidian,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },

  // ── Navbar ──
  nav: {
    position: 'sticky',
    top: 0,
    zIndex: 50,
    background: 'rgba(9, 9, 11, 0.88)',
    backdropFilter: 'blur(12px)',
    WebkitBackdropFilter: 'blur(12px)',
    borderBottom: `1px solid ${C.border}`,
  },
  navInner: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '12px 24px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 16,
    flexWrap: 'wrap',
  },
  navBrand: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    textDecoration: 'none',
    color: C.heading,
  },
  navLogoText: { fontSize: 17, fontWeight: 600 },
  navLinks: { display: 'flex', gap: 32 },
  navLink: {
    fontSize: 15,
    color: C.muted,
    textDecoration: 'none',
    transition: 'color 0.15s, border-color 0.15s',
    paddingBottom: 4,
    borderBottom: '2px solid transparent',
  },
  navLinkActive: {
    color: '#ffffff',
    fontWeight: 600,
    borderBottom: `2px solid ${C.cyan}`,
  },
  navActions: { display: 'flex', alignItems: 'center', gap: 8 },
  navBtnGhost: {
    fontSize: 15,
    fontWeight: 500,
    color: '#e4e4e7',
    textDecoration: 'none',
    padding: '12px 14px',
  },

  // ── Hero ──
  hero: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '72px 24px 88px',
    display: 'grid',
    gridTemplateColumns: fit(340),
    gap: 56,
    alignItems: 'center',
  },
  heroContent: {
    animation: 'landing-fade-up 0.6s ease-out',
  },
  heroBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 14px',
    borderRadius: 100,
    border: '1px solid rgba(6, 182, 212, 0.3)',
    background: 'rgba(6, 182, 212, 0.08)',
    color: C.cyanText,
    fontSize: 13,
    fontWeight: 500,
    marginBottom: 24,
  },
  heroTitle: {
    fontFamily: SERIF,
    fontSize: 'clamp(40px, 5.2vw, 68px)',
    fontWeight: 500,
    lineHeight: 1.04,
    letterSpacing: '-0.02em',
    color: C.heading,
    margin: '0 0 24px',
  },
  heroTitleAccent: { color: C.cyanText, fontStyle: 'italic' },
  heroSubtitle: {
    fontSize: 18,
    color: C.muted,
    maxWidth: 520,
    margin: '0 0 32px',
  },
  heroButtons: { display: 'flex', flexWrap: 'wrap', gap: 12 },

  // ── Chat mockup ──
  mockupWrapper: {
    animation: 'landing-fade-up 0.8s ease-out 0.15s both',
  },
  mockupCard: {
    borderRadius: 16,
    border: `1px solid ${C.border}`,
    background: C.obsidian,
    overflow: 'hidden',
    boxShadow: '0 24px 64px rgba(0, 0, 0, 0.6)',
  },
  mockupHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: `1px solid ${C.border}`,
    background: C.panel,
  },
  mockupDots: { display: 'flex', gap: 6 },
  mockupDot: { display: 'inline-block', width: 10, height: 10, borderRadius: '50%' },
  mockupHeaderTitle: { fontSize: 12, fontWeight: 500, color: C.muted },
  mockupBody: {
    padding: '20px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
  },
  msgUserRow: { display: 'flex', justifyContent: 'flex-end' },
  bubbleUser: {
    maxWidth: '80%',
    padding: '12px 16px',
    borderRadius: '14px 14px 4px 14px',
    background: 'rgba(6, 182, 212, 0.12)',
    border: '1px solid rgba(6, 182, 212, 0.25)',
    color: '#e4e4e7',
    fontSize: 14,
  },
  msgAiRow: { display: 'flex', gap: 10, alignItems: 'flex-start' },
  aiAvatar: {
    width: 28,
    height: 28,
    borderRadius: 8,
    background: '#fafafa',
    color: C.obsidian,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 2,
  },
  bubbleAi: {
    maxWidth: '92%',
    padding: '12px 16px',
    borderRadius: '14px 14px 14px 4px',
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    color: C.body,
    fontSize: 14,
  },
  aiLabel: { fontSize: 12, fontWeight: 600, color: C.cyanText, marginBottom: 4 },
  metricChip: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    width: 'fit-content',
    maxWidth: '100%',
    marginTop: 12,
    padding: '6px 12px',
    borderRadius: 8,
    background: 'rgba(245, 158, 11, 0.1)',
    border: '1px solid rgba(245, 158, 11, 0.25)',
    fontSize: 12,
    fontWeight: 500,
    color: C.amber,
  },
  chipDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#f59e0b',
    flexShrink: 0,
  },
  typing: {
    display: 'flex',
    gap: 4,
    padding: '12px 16px',
    borderRadius: '14px 14px 14px 4px',
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
  },
  typingDot: (delay) => ({
    display: 'inline-block',
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#71717a',
    animation: `landing-typing 1.4s infinite ${delay}s`,
  }),
  mockupInputBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 16px',
    borderTop: `1px solid ${C.border}`,
    background: C.panel,
  },
  mockupInput: {
    flex: 1,
    minWidth: 0,
    boxSizing: 'border-box',
    padding: '12px 14px',
    borderRadius: 10,
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    color: C.muted,
    fontSize: 14,
  },
  mockupSendBtn: {
    width: 44,
    height: 44,
    borderRadius: 10,
    background: C.cyan,
    color: C.obsidian,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
};
