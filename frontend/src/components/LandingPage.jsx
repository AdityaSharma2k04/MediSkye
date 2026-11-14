import React, { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Trans, useTranslation } from 'react-i18next';
import { getSavedAuthSession } from '../services/firebase';
import useIntersectionObserver from '../hooks/useIntersectionObserver';
import { BrandLockup, BrandMark } from './workbench/Brand';
import RangeBar from './clinical/RangeBar';
import StatusPill from './clinical/StatusPill';
import DeltaIndicator from './clinical/DeltaIndicator';
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
    const session = getSavedAuthSession();
    if (session) {
      navigate('/chat', { replace: true });
      return;
    }
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

  const navLink = (id, label) => (
    <a
      href={`#${id}`}
      onClick={(e) => handleNavClick(e, id)}
      className={`landing-link text-[14px] text-ink-mute hover:text-white transition-colors pb-1 border-b-2 border-transparent ${
        activeSection === id ? 'landing-link-active' : ''
      }`}
      aria-current={activeSection === id ? 'page' : undefined}
    >
      {label}
    </a>
  );

  return (
    <div className="landing min-h-app bg-obsidian text-ink font-sans overflow-x-clip">
      {/* ━━━━━━━━━━ NAVBAR ━━━━━━━━━━ */}
      <nav id="landing-nav" aria-label="Main Navigation" className="sticky top-0 z-50 bg-obsidian/80 backdrop-blur-xl border-b border-white/[0.06] pt-safe">
        <div className="max-w-[1200px] mx-auto h-16 px-5 sm:px-6 flex items-center justify-between gap-4">
          <Link to="/" aria-label="MediSkye Home" className="shrink-0">
            <BrandLockup size={30} />
          </Link>

          <div className="landing-nav-links hidden md:flex items-center gap-8">
            {navLink('features', t('landing.nav_features', 'Features'))}
            {navLink('how-it-works', t('landing.nav_how_it_works', 'How it works'))}
            {navLink('safety', t('landing.nav_safety', 'Safety'))}
          </div>

          <div className="flex items-center gap-1.5 sm:gap-2">
            <Link to="/login" id="landing-login-btn" className="landing-link ms-tap inline-flex items-center h-10 px-3.5 rounded-xl text-[14px] font-medium text-ink-soft hover:text-white transition">
              {t('landing.nav_sign_in', 'Sign in')}
            </Link>
            <Link
              to="/register"
              id="landing-register-btn"
              className="landing-btn-primary ms-tap inline-flex items-center h-10 px-4 rounded-xl text-[14px] font-semibold bg-clinical-cyan text-slate-950 hover:bg-cyan-300 transition"
            >
              {t('landing.nav_get_started', 'Get started')}
            </Link>
          </div>
        </div>
      </nav>

      {/* ━━━━━━━━━━ HERO ━━━━━━━━━━ */}
      <section ref={heroRef} id="hero" className="relative">
        <div className="pointer-events-none absolute inset-0 bg-ambient opacity-90" aria-hidden="true" />
        <div className="relative max-w-[1200px] mx-auto px-5 sm:px-6 pt-14 sm:pt-20 pb-20 sm:pb-24 grid lg:grid-cols-[minmax(0,1fr)_minmax(0,1.02fr)] gap-12 lg:gap-16 items-center">
          <div className="landing-hero-copy">
            <p className="inline-flex items-center gap-2 text-[13px] text-cyan-200 mb-6">
              <span className="w-1.5 h-1.5 rounded-full bg-clinical-cyan" aria-hidden="true" />
              {t('landing.hero_badge', 'Clinical AI Interpretation')}
            </p>

            <h1 className="font-display ms-display tracking-tight text-[44px] sm:text-[60px] lg:text-[68px] leading-[1.02] text-white mb-6 max-w-[14ch]">
              <Trans
                i18nKey="landing.hero_title_accent"
                defaults="Understand your medical reports <accent>in seconds.</accent>"
                components={{
                  accent: (
                    <span className="bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-500 bg-clip-text text-transparent" />
                  ),
                }}
              />
            </h1>

            <p className="text-[17px] sm:text-lg leading-relaxed text-ink-mute max-w-[52ch] mb-9">
              {t(
                'landing.hero_subtitle',
                'Upload any lab report or medical document. MediSkye reads it, extracts the key metrics, and explains everything in plain language, so you walk into every doctor visit fully informed.'
              )}
            </p>

            <div className="flex flex-wrap gap-3">
              <Link
                to="/register"
                id="hero-cta-primary"
                className="landing-btn-primary ms-tap inline-flex items-center justify-center h-12 px-6 rounded-xl text-[15px] font-semibold bg-clinical-cyan text-slate-950 hover:bg-cyan-300 transition shadow-[0_12px_32px_-12px_rgba(6,182,212,0.8)]"
              >
                {t('landing.start_free', 'Start for free')}
              </Link>
              <a
                href="#how-it-works"
                onClick={(e) => handleNavClick(e, 'how-it-works')}
                className="landing-btn-secondary ms-tap inline-flex items-center justify-center h-12 px-6 rounded-xl text-[15px] font-medium text-ink-soft border border-white/[0.12] hover:border-white/[0.24] hover:text-white transition"
              >
                {t('landing.see_how_it_works', 'See how it works')}
              </a>
            </div>

            <dl className="mt-12 grid grid-cols-3 gap-6 max-w-md text-[13px]">
              <div>
                <dt className="text-ink-faint">Lab tests identified</dt>
                <dd className="mt-1 text-white">Reference range &amp; change over time</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Family profiles</dt>
                <dd className="mt-1 text-white">Self + dependents</dd>
              </div>
              <div>
                <dt className="text-ink-faint">Languages</dt>
                <dd className="mt-1 text-white">English, हिंदी</dd>
              </div>
            </dl>
          </div>

          <WorkbenchPreview />
        </div>
      </section>

      {/* ━━━━━━━━━━ FEATURES ━━━━━━━━━━ */}
      <DeferredSection id="features" minHeight={560} className="scroll-mt-24 md:scroll-mt-32" forceVisible={Boolean(forcedSections['features'])}>
        <Suspense fallback={<div style={{ minHeight: 560 }} aria-hidden="true" />}>
          <FeaturesSection />
        </Suspense>
      </DeferredSection>

      {/* ━━━━━━━━━━ HOW IT WORKS ━━━━━━━━━━ */}
      <DeferredSection id="how-it-works" minHeight={780} className="scroll-mt-24 md:scroll-mt-32" forceVisible={Boolean(forcedSections['how-it-works'])}>
        <Suspense fallback={<div style={{ minHeight: 780 }} aria-hidden="true" />}>
          <HowItWorksSection />
        </Suspense>
      </DeferredSection>

      {/* ━━━━━━━━━━ SAFETY ━━━━━━━━━━ */}
      <DeferredSection id="safety" minHeight={620} className="scroll-mt-24 md:scroll-mt-32" forceVisible={Boolean(forcedSections['safety'])}>
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

/* ─── Hero: live workbench preview (static data, mirrors the real inspector) ─── */
const PREVIEW_ROWS = [
  { test: 'Vitamin D (25-OH)', value: '24.0', unit: 'ng/mL', range: '30–100', status: 'Low', previous_value: '44.0', delta_pct: -45.5 },
  { test: 'Hemoglobin', value: '11.6', unit: 'g/dL', range: '12.0–15.5', status: 'Low', previous_value: '13.1', delta_pct: -11.5 },
  { test: 'Ferritin', value: '238', unit: 'pg/mL', range: '200–900', status: 'Normal', previous_value: '310', delta_pct: -23.2 },
  { test: 'HbA1c', value: '5.4', unit: '%', range: '4.0–5.6', status: 'Normal' },
  { test: 'LDL Cholesterol', value: '162', unit: 'mg/dL', range: '<100', status: 'High', previous_value: '148', delta_pct: 9.5 },
];

function WorkbenchPreview() {
  return (
    <div className="relative" aria-hidden="true">
      <div className="absolute -inset-6 rounded-[40px] bg-[radial-gradient(closest-side,rgba(6,182,212,0.14),transparent)] blur-2xl" />
      <div className="relative rounded-[28px] ms-glass overflow-hidden">
        <div className="flex items-center justify-between gap-3 px-5 h-12 border-b border-white/[0.07]">
          <div className="flex items-center gap-2.5 min-w-0">
            <BrandMark size={22} />
            <span className="text-[13px] font-medium text-white truncate">Follow-up panel</span>
            <span className="ms-num text-[11px] text-ink-faint shrink-0">04 Nov 2026</span>
          </div>
          <span className="text-[11px] px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/25 text-amber-200 shrink-0">3 need attention</span>
        </div>

        <ul className="px-5 py-4 space-y-4">
          {PREVIEW_ROWS.map((row, i) => (
            <li key={row.test} className="landing-preview-row" style={{ animationDelay: `${120 + i * 90}ms` }}>
              <div className="flex items-center justify-between gap-3 mb-1">
                <span className="text-[13px] text-ink-soft truncate">{row.test}</span>
                <span className="flex items-center gap-2 shrink-0">
                  {row.previous_value && <DeltaIndicator row={row} compact showValues={false} />}
                  <StatusPill row={row} size="sm" />
                </span>
              </div>
              <div className="flex items-center gap-4">
                <span className="ms-num text-[15px] text-white w-[92px] shrink-0">
                  {row.value} <span className="text-[11px] text-ink-faint">{row.unit}</span>
                </span>
                <RangeBar row={row} size="sm" className="flex-1" />
              </div>
            </li>
          ))}
        </ul>

        <div className="mx-5 mb-5 rounded-2xl bg-white/[0.03] border border-white/[0.07] p-4">
          <div className="flex items-center gap-2 mb-1.5 text-xs">
            <span className="font-semibold text-ink-soft">MediSkye AI</span>
            <span className="text-ink-faint">explains</span>
          </div>
          <p className="text-[13.5px] leading-relaxed text-ink-soft">
            Your vitamin D fell from <span className="ms-num text-white">44.0</span> to <span className="ms-num text-amber-200">24.0 ng/mL</span> and is now below range. With hemoglobin also slightly low, it is worth asking your doctor whether an iron study and a supplement review make sense.
          </p>
        </div>
      </div>
    </div>
  );
}

/* ─── CSS: interaction states, responsive, reduced motion ─── */
const css = `
  html { scroll-padding-top: 96px; }

  @keyframes landing-row-in {
    from { opacity: 0; transform: translateY(6px); }
    to { opacity: 1; transform: translateY(0); }
  }
  .landing-preview-row { animation: landing-row-in 0.5s cubic-bezier(0.22, 1, 0.36, 1) both; }

  .fade-in-section {
    opacity: 0;
    transform: translateY(20px);
    transition: opacity 0.6s cubic-bezier(0.16, 1, 0.3, 1), transform 0.6s cubic-bezier(0.16, 1, 0.3, 1);
    will-change: opacity, transform;
  }
  .fade-in-section.is-visible { opacity: 1; transform: translateY(0); }

  .landing-link-active {
    color: #ffffff !important;
    border-bottom-color: #06b6d4 !important;
  }
  .landing a:focus-visible {
    outline: 2px solid #22d3ee;
    outline-offset: 3px;
    border-radius: 8px;
  }

  @media (prefers-reduced-motion: reduce) {
    .landing *, .landing *::before, .landing *::after {
      animation: none !important;
      transition: none !important;
    }
    html { scroll-behavior: auto; }
  }
`;
