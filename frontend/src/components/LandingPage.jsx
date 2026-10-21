import React, { useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

/* ─── Palette (mirrors tailwind.config: obsidian + medical) ─── */
const C = {
  obsidian: '#09090b',
  obsidianLight: '#18181b',
  panel: '#111113',
  border: '#27272a',
  borderStrong: '#3f3f46',
  cyan: '#06b6d4', // medical.cyan
  cyanDark: '#0891b2', // medical.dark
  cyanText: '#22d3ee', // cyan tint for text on dark (AA contrast)
  heading: '#fafafa',
  body: '#d4d4d8',
  muted: '#a1a1aa',
  amber: '#fbbf24',
  green: '#34d399',
  red: '#f87171',
};

const SERIF = "'Newsreader', Georgia, serif";
const SANS = "'Figtree', system-ui, -apple-system, sans-serif";

// Auto-fit grid that never overflows narrow phones
const fit = (min) => `repeat(auto-fit, minmax(min(100%, ${min}px), 1fr))`;

/* ─── Icons (inline SVGs, zero external icon dependencies) ─── */
const Icon = ({ size = 24, strokeWidth = 1.5, children }) => (
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

const ActivityIcon = (p) => (
  <Icon strokeWidth={2} {...p}>
    <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
  </Icon>
);

const FlaskIcon = (p) => (
  <Icon {...p}>
    <path d="M9 3h6" />
    <path d="M10 9V3" />
    <path d="M14 9V3" />
    <path d="M6 21h12" />
    <path d="M10 9l-4 8c-.7 1.3.13 3 1.76 3h8.48c1.63 0 2.46-1.7 1.76-3L14 9" />
  </Icon>
);

const BrainIcon = (p) => (
  <Icon {...p}>
    <path d="M9.5 2A5.5 5.5 0 0 0 4 7.5c0 1.28.44 2.46 1.18 3.39" />
    <path d="M14.5 2A5.5 5.5 0 0 1 20 7.5c0 1.28-.44 2.46-1.18 3.39" />
    <path d="M5.18 10.89A5.5 5.5 0 0 0 4 14.5 5.5 5.5 0 0 0 9.5 20h1" />
    <path d="M18.82 10.89A5.5 5.5 0 0 1 20 14.5a5.5 5.5 0 0 1-5.5 5.5h-1" />
    <path d="M12 2v20" />
  </Icon>
);

const ScanIcon = (p) => (
  <Icon {...p}>
    <path d="M3 7V5a2 2 0 0 1 2-2h2" />
    <path d="M17 3h2a2 2 0 0 1 2 2v2" />
    <path d="M21 17v2a2 2 0 0 1-2 2h-2" />
    <path d="M7 21H5a2 2 0 0 1-2-2v-2" />
    <line x1="7" y1="12" x2="17" y2="12" />
  </Icon>
);

const UploadIcon = (p) => (
  <Icon {...p}>
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </Icon>
);

const SparklesIcon = (p) => (
  <Icon {...p}>
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
  </Icon>
);

const SendIcon = (p) => (
  <Icon strokeWidth={2} {...p}>
    <line x1="22" y1="2" x2="11" y2="13" />
    <polygon points="22 2 15 22 11 13 2 9 22 2" />
  </Icon>
);

/* ─── Content ─── */
const FEATURES = [
  {
    icon: <FlaskIcon size={22} />,
    title: 'Lab metrics dashboard',
    description:
      'Automatically extracts biomarkers like Hemoglobin, TSH, LDL, and Vitamin D, with normal range comparisons and clear clinical status indicators.',
  },
  {
    icon: <BrainIcon size={22} />,
    title: 'Remembers your history',
    description:
      'MediSkye securely recalls past conversations and uploaded reports, so you can ask follow-up questions weeks later without re-uploading.',
  },
  {
    icon: <ScanIcon size={22} />,
    title: 'Scans PDFs and images',
    description:
      'Upload PDFs, camera photos, or scanned lab slips. Our high-fidelity OCR reads printed hospital reports as well as clinic prescriptions.',
  },
];

const METRICS = [
  { name: 'Hemoglobin', value: '11.2 g/dL', status: 'Borderline low', color: C.amber },
  { name: 'TSH', value: '2.1 mIU/L', status: 'Normal', color: C.green },
  { name: 'LDL', value: '142 mg/dL', status: 'High', color: C.red },
];

const CAN = [
  'Explain each metric and test in plain language',
  'Flag values outside the reference range',
  'Summarize results to prepare for your doctor visit',
];

const CANNOT = [
  'Diagnose medical conditions independently',
  'Replace professional medical advice',
  'Make prescription or treatment decisions',
];

export default function LandingPage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const heroRef = useRef(null);

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
            <a href="#features" style={styles.navLink} className="landing-link">
              {t('landing.nav_features', 'Features')}
            </a>
            <a href="#how-it-works" style={styles.navLink} className="landing-link">
              {t('landing.nav_how_it_works', 'How it works')}
            </a>
            <a href="#safety" style={styles.navLink} className="landing-link">
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
            {t('landing.hero_title', 'Understand your medical reports in plain English')}
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
            <a href="#how-it-works" style={styles.btnSecondary} className="landing-btn-secondary">
              {t('landing.see_how_it_works', 'See how it works')}
            </a>
          </div>
        </div>

        <ChatMockup />
      </section>

      {/* ━━━━━━━━━━ FEATURES ━━━━━━━━━━ */}
      <section style={styles.featuresSection} id="features">
        <p style={styles.eyebrow}>Features</p>
        <h2 style={{ ...styles.sectionTitle, maxWidth: 680 }}>
          Everything you need to understand your health
        </h2>
        <p style={{ ...styles.sectionSubtitle, maxWidth: 600, marginBottom: 48 }}>
          From instant lab metric extraction to intelligent follow-up questions, MediSkye
          turns complex medical reports into clear, actionable insight.
        </p>

        <div style={styles.featuresGrid}>
          {FEATURES.map((f) => (
            <FeatureCard key={f.title} {...f} />
          ))}
        </div>
      </section>

      {/* ━━━━━━━━━━ HOW IT WORKS ━━━━━━━━━━ */}
      <section style={styles.howSection} id="how-it-works">
        <div style={styles.howInner}>
          <p style={styles.eyebrow}>How it works</p>
          <h2 style={styles.sectionTitle}>Three steps to clarity</h2>
          <p style={{ ...styles.sectionSubtitle, marginBottom: 48 }}>
            No medical degree required. Just upload, ask, and understand.
          </p>

          <div style={styles.stepsGrid}>
            <StepCard
              number="01"
              visual={<UploadVisual />}
              title="Upload your report"
              description="Drag and drop a PDF, photo, or scanned image of your lab results. Any standard format works."
            />
            <StepCard
              number="02"
              visual={<ExtractVisual />}
              title="AI analyzes it"
              description="Gemini extracts every metric, flags abnormal values, and prepares a clear, plain-language summary."
            />
            <StepCard
              number="03"
              visual={<AskVisual />}
              title="Ask anything"
              description="Chat about your results. Ask follow-ups, compare past reports, or get a doctor-visit summary."
            />
          </div>
        </div>
      </section>

      {/* ━━━━━━━━━━ SAFETY ━━━━━━━━━━ */}
      <section style={styles.safetySection} id="safety">
        <div>
          <p style={styles.eyebrow}>Safety</p>
          <h2 style={styles.sectionTitle}>Built to inform, not to diagnose</h2>
          <p style={{ ...styles.sectionSubtitle, margin: 0 }}>
            MediSkye is an AI assistant for informational purposes. It helps you understand
            your results and prepare better questions. Your doctor makes the clinical decisions.
          </p>
        </div>

        <div style={styles.safetyCards}>
          <ListCard title={t('landing.safety_can_title', 'MediSkye can')} color={C.cyanText} items={CAN} isAllowed={true} />
          <ListCard title={t('landing.safety_cannot_title', 'MediSkye cannot')} color={C.red} items={CANNOT} isAllowed={false} />
        </div>
      </section>

      {/* ━━━━━━━━━━ CTA ━━━━━━━━━━ */}
      <section style={styles.ctaSection}>
        <div style={styles.ctaCard}>
          <h2 style={{ ...styles.sectionTitle, margin: '0 auto 12px', maxWidth: 620 }}>
            Ready to understand your health?
          </h2>
          <p style={styles.ctaSubtitle}>
            Upload your first report and see it explained in plain language.
          </p>
          <Link
            to="/register"
            style={styles.btnPrimary}
            className="landing-btn-primary"
            id="cta-register-btn"
          >
            Get started, it’s free
          </Link>
        </div>
      </section>

      {/* ━━━━━━━━━━ FOOTER ━━━━━━━━━━ */}
      <footer style={styles.footer} id="landing-footer">
        <div style={styles.footerInner}>
          <div style={styles.footerTop}>
            <div style={styles.footerBrand}>
              <div style={styles.footerLogoRow}>
                <div style={{ ...styles.logoBox, width: 28, height: 28, borderRadius: 7 }}>
                  <ActivityIcon size={16} />
                </div>
                <span style={styles.footerLogoText}>MediSkye</span>
              </div>
              <p style={styles.footerTagline}>
                {t('landing.footer_tagline', 'AI-powered medical report interpretation.')}
              </p>
              <p style={styles.footerDisclaimer}>
                {t(
                  'landing.footer_disclaimer',
                  'MediSkye is an AI assistant for informational purposes only. It does not provide medical diagnoses or replace professional medical advice. Always consult a qualified healthcare provider for clinical decisions.'
                )}
              </p>
              <p style={styles.footerCopyright}>
                {t('landing.footer_copyright', '© 2026 MediSkye. All rights reserved.')}
              </p>
            </div>

            <div style={styles.footerLinks}>
              <div style={styles.footerCol}>
                <h4 style={styles.footerColTitle}>Product</h4>
                <a href="#features" style={styles.footerLink} className="landing-link">
                  Features
                </a>
                <a href="#how-it-works" style={styles.footerLink} className="landing-link">
                  How it works
                </a>
                <a href="#safety" style={styles.footerLink} className="landing-link">
                  Safety
                </a>
              </div>
              <div style={styles.footerCol}>
                <h4 style={styles.footerColTitle}>Account</h4>
                <Link to="/login" style={styles.footerLink} className="landing-link">
                  Sign in
                </Link>
                <Link to="/register" style={styles.footerLink} className="landing-link">
                  Create account
                </Link>
              </div>
            </div>
          </div>
        </div>
      </footer>

      {/* Inline CSS: fonts, keyframes, hover/focus, responsive */}
      <style>{css}</style>
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

/* ─── How-it-works illustrations (decorative) ─── */
function UploadVisual() {
  return (
    <div style={styles.visual} aria-hidden="true">
      <div style={styles.dropzone}>
        <UploadIcon size={22} />
        Drop a PDF, photo or scan
      </div>
      <div style={styles.fileRow}>
        <span>blood-panel.pdf</span>
        <span style={styles.progressTrack}>
          <span style={styles.progressFill} />
        </span>
        <span style={{ color: C.muted }}>72%</span>
      </div>
    </div>
  );
}

function ExtractVisual() {
  return (
    <div style={{ ...styles.visual, justifyContent: 'center', gap: 6 }} aria-hidden="true">
      <div style={styles.extractHeader}>
        <SparklesIcon size={14} />
        Extracting metrics
      </div>
      {METRICS.map((m) => (
        <div key={m.name} style={styles.metricRow}>
          <span>
            {m.name} <span style={{ color: C.muted }}>{m.value}</span>
          </span>
          <span style={{ color: m.color, fontWeight: 600 }}>{m.status}</span>
        </div>
      ))}
    </div>
  );
}

function AskVisual() {
  return (
    <div style={{ ...styles.visual, justifyContent: 'center', gap: 8 }} aria-hidden="true">
      <div style={styles.miniUser}>Summarize this for my doctor visit</div>
      <div style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
        <div style={{ ...styles.aiAvatar, width: 22, height: 22, borderRadius: 6, marginTop: 0 }}>
          <ActivityIcon size={12} />
        </div>
        <div style={styles.miniAi}>Here are 3 points worth raising with your doctor.</div>
      </div>
      <div style={styles.miniInput}>
        Ask a follow-up...
        <span style={styles.miniSend} />
      </div>
    </div>
  );
}

/* ─── Sub-components ─── */
function FeatureCard({ icon, title, description }) {
  return (
    <div style={styles.featureCard} className="landing-feature-card">
      <div style={styles.featureIconBox}>{icon}</div>
      <h3 style={styles.featureTitle}>{title}</h3>
      <p style={styles.featureDesc}>{description}</p>
    </div>
  );
}

function StepCard({ number, visual, title, description }) {
  return (
    <div style={styles.stepCard} className="landing-step-card">
      {visual}
      <div style={styles.stepNumber}>{number}</div>
      <h3 style={styles.stepTitle}>{title}</h3>
      <p style={styles.stepDesc}>{description}</p>
    </div>
  );
}

function ListCard({ title, color, items, isAllowed }) {
  return (
    <div style={styles.listCard} className="landing-list-card">
      <h3 style={{ ...styles.listCardTitle, color }}>{title}</h3>
      <ul style={styles.list}>
        {items.map((item) => (
          <li key={item} style={styles.listItem}>
            <span style={{ color, marginRight: 10, fontWeight: 700, display: 'inline-block' }}>
              {isAllowed ? '✓' : '✕'}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/* ─── CSS: fonts, keyframes, hover/focus, responsive ─── */
const css = `
  @import url('https://fonts.googleapis.com/css2?family=Figtree:wght@400;500;600&family=Newsreader:ital,opsz,wght@0,6..72,500;1,6..72,500&display=swap');

  html { scroll-behavior: smooth; scroll-padding-top: 72px; }

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

  .landing-mockup { animation: landing-float 6s ease-in-out infinite; }

  .landing-link:hover { color: #fafafa !important; }
  .landing-btn-primary { transition: transform 0.15s ease, box-shadow 0.15s ease, background-color 0.15s ease; }
  .landing-btn-primary:hover {
    transform: translateY(-1px);
    box-shadow: 0 8px 24px rgba(6, 182, 212, 0.28);
  }
  .landing-btn-secondary { transition: border-color 0.15s ease, color 0.15s ease, background-color 0.15s ease; }
  .landing-btn-secondary:hover { border-color: #52525b !important; color: #fafafa !important; background-color: rgba(255, 255, 255, 0.03); }

  .landing-feature-card { transition: transform 0.2s ease, border-color 0.2s ease; }
  .landing-feature-card:hover { transform: translateY(-2px); }

  .landing-step-card { transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease; }
  .landing-step-card:hover {
    transform: translateY(-2px);
    border-color: #3f3f46 !important;
    box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4);
  }

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
  navLink: { fontSize: 15, color: C.muted, textDecoration: 'none', transition: 'color 0.15s' },
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
    lineHeight: 1.05,
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

  // ── Features ──
  featuresSection: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '40px 24px 96px',
  },
  featuresGrid: {
    display: 'grid',
    gridTemplateColumns: fit(280),
    gap: 40,
  },
  featureCard: {
    borderTop: `1px solid ${C.borderStrong}`,
    paddingTop: 24,
  },
  featureIconBox: {
    width: 44,
    height: 44,
    borderRadius: 12,
    background: 'rgba(6, 182, 212, 0.12)',
    color: C.cyanText,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  featureTitle: { fontSize: 19, fontWeight: 600, color: C.heading, margin: '0 0 10px' },
  featureDesc: { fontSize: 16, color: C.muted, margin: 0 },

  // ── How it works ──
  howSection: {
    background: C.panel,
    borderTop: `1px solid ${C.border}`,
    borderBottom: `1px solid ${C.border}`,
  },
  howInner: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '88px 24px',
  },
  stepsGrid: {
    display: 'grid',
    gridTemplateColumns: fit(260),
    gap: 24,
  },
  stepCard: {
    padding: 32,
    borderRadius: 16,
    border: `1px solid ${C.border}`,
    background: C.obsidianLight,
  },
  stepNumber: {
    fontFamily: SERIF,
    fontSize: 56,
    lineHeight: 1,
    color: C.cyan,
    marginBottom: 12,
  },
  stepTitle: { fontSize: 19, fontWeight: 600, color: C.heading, margin: '0 0 8px' },
  stepDesc: { fontSize: 16, color: C.muted, margin: 0 },

  // Step illustrations
  visual: {
    height: 168,
    boxSizing: 'border-box',
    marginBottom: 24,
    padding: 14,
    borderRadius: 12,
    background: C.obsidian,
    border: `1px solid ${C.border}`,
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  dropzone: {
    flex: 1,
    border: '1.5px dashed rgba(6, 182, 212, 0.45)',
    borderRadius: 10,
    background: 'rgba(6, 182, 212, 0.06)',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 6,
    color: C.cyanText,
    fontSize: 13,
    fontWeight: 500,
  },
  fileRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    padding: '8px 10px',
    borderRadius: 8,
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    fontSize: 12,
    color: C.body,
  },
  progressTrack: {
    flex: 1,
    height: 4,
    borderRadius: 2,
    background: C.border,
    overflow: 'hidden',
  },
  progressFill: { display: 'block', width: '72%', height: '100%', background: C.cyan },
  extractHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 12,
    fontWeight: 600,
    color: C.cyanText,
    marginBottom: 2,
  },
  metricRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    padding: '5px 10px',
    borderRadius: 8,
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    fontSize: 12,
    color: C.body,
  },
  miniUser: {
    alignSelf: 'flex-end',
    maxWidth: '85%',
    padding: '7px 12px',
    borderRadius: '12px 12px 4px 12px',
    background: 'rgba(6, 182, 212, 0.12)',
    border: '1px solid rgba(6, 182, 212, 0.25)',
    fontSize: 12,
    color: '#e4e4e7',
  },
  miniAi: {
    padding: '7px 12px',
    borderRadius: '12px 12px 12px 4px',
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    fontSize: 12,
    color: C.body,
  },
  miniInput: {
    height: 30,
    boxSizing: 'border-box',
    borderRadius: 8,
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '0 6px 0 10px',
    fontSize: 12,
    color: C.muted,
  },
  miniSend: { width: 20, height: 20, borderRadius: 6, background: C.cyan },

  // ── Safety ──
  safetySection: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '96px 24px',
    display: 'grid',
    gridTemplateColumns: fit(320),
    gap: 56,
    alignItems: 'start',
  },
  safetyCards: {
    display: 'grid',
    gridTemplateColumns: fit(220),
    gap: 16,
  },
  listCard: {
    padding: 24,
    borderRadius: 16,
    border: `1px solid ${C.border}`,
    background: C.obsidianLight,
  },
  listCardTitle: { fontSize: 16, fontWeight: 600, margin: '0 0 12px' },
  list: { listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 10 },
  listItem: { color: C.body, fontSize: 15, display: 'flex', alignItems: 'flex-start' },

  // ── CTA ──
  ctaSection: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '0 24px 96px',
  },
  ctaCard: {
    background: C.obsidianLight,
    border: '1px solid rgba(6, 182, 212, 0.35)',
    borderRadius: 24,
    padding: '64px 32px',
    textAlign: 'center',
    boxShadow: '0 20px 48px rgba(0, 0, 0, 0.5)',
  },
  ctaSubtitle: { fontSize: 17, color: C.muted, margin: '0 0 28px' },

  // ── Footer ──
  footer: { borderTop: `1px solid ${C.border}` },
  footerInner: { maxWidth: 1200, margin: '0 auto', padding: '40px 24px 36px' },
  footerTop: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: 40,
  },
  footerBrand: { maxWidth: 520 },
  footerLogoRow: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 },
  footerLogoText: { fontSize: 16, fontWeight: 600, color: '#fafafa' },
  footerTagline: { fontSize: 14, color: C.muted, margin: '0 0 14px' },
  footerDisclaimer: { fontSize: 13, color: C.muted, margin: '0 0 10px', lineHeight: 1.6 },
  footerCopyright: { fontSize: 13, color: C.muted, margin: 0 },
  footerLinks: { display: 'flex', gap: '32px 64px', flexWrap: 'wrap' },
  footerCol: { display: 'flex', flexDirection: 'column', gap: 8 },
  footerColTitle: { fontSize: 14, fontWeight: 600, color: '#fafafa', margin: 0 },
  footerLink: { fontSize: 14, color: C.muted, textDecoration: 'none', transition: 'color 0.15s' },
};
