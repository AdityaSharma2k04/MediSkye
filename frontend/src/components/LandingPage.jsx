import React, { useEffect, useRef } from 'react';
import { Link, useNavigate } from 'react-router-dom';

/* ─── Icon components (inline SVGs to avoid heavy deps) ─── */
const ActivityIcon = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
  </svg>
);

const FlaskIcon = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 3h6" /><path d="M10 9V3" /><path d="M14 9V3" />
    <path d="M6 21h12" /><path d="M10 9l-4 8c-.7 1.3.13 3 1.76 3h8.48c1.63 0 2.46-1.7 1.76-3L14 9" />
  </svg>
);

const BrainIcon = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9.5 2A5.5 5.5 0 0 0 4 7.5c0 1.28.44 2.46 1.18 3.39" />
    <path d="M14.5 2A5.5 5.5 0 0 1 20 7.5c0 1.28-.44 2.46-1.18 3.39" />
    <path d="M5.18 10.89A5.5 5.5 0 0 0 4 14.5 5.5 5.5 0 0 0 9.5 20h1" />
    <path d="M18.82 10.89A5.5 5.5 0 0 1 20 14.5a5.5 5.5 0 0 1-5.5 5.5h-1" />
    <path d="M12 2v20" />
  </svg>
);

const ScanIcon = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 7V5a2 2 0 0 1 2-2h2" /><path d="M17 3h2a2 2 0 0 1 2 2v2" />
    <path d="M21 17v2a2 2 0 0 1-2 2h-2" /><path d="M7 21H5a2 2 0 0 1-2-2v-2" />
    <line x1="7" y1="12" x2="17" y2="12" />
  </svg>
);

const UploadIcon = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const SparklesIcon = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z" />
  </svg>
);

const MessageIcon = ({ size = 24 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
    <path d="m3 21 1.9-5.7a8.5 8.5 0 1 1 3.8 3.8z" />
  </svg>
);

const ChevronRight = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);


export default function LandingPage() {
  const navigate = useNavigate();
  const heroRef = useRef(null);

  // If already authenticated, redirect to /chat
  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        const payload = JSON.parse(atob(token.split('.')[1]));
        if (payload.exp && payload.exp * 1000 > Date.now()) {
          navigate('/chat', { replace: true });
          return;
        }
      } catch (_) {
        // invalid token, stay on landing
      }
    }
  }, [navigate]);

  // Apply dark mode
  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  return (
    <div style={styles.page}>
      {/* ──── Animated background ──── */}
      <div style={styles.bgGradient} />
      <div style={styles.bgGrid} />

      {/* ━━━━━━━━━━ NAVBAR ━━━━━━━━━━ */}
      <nav style={styles.nav} id="landing-nav">
        <div style={styles.navInner}>
          <Link to="/" style={styles.navBrand} aria-label="MediSkye Home">
            <div style={styles.navLogoBox}>
              <ActivityIcon size={18} />
            </div>
            <span style={styles.navLogoText}>MediSkye</span>
          </Link>

          <div style={styles.navLinks}>
            <a href="#features" style={styles.navLink}>Features</a>
            <a href="#how-it-works" style={styles.navLink}>How it works</a>
          </div>

          <div style={styles.navActions}>
            <Link to="/login" style={styles.navBtnGhost} id="landing-login-btn">Sign in</Link>
            <Link to="/register" style={styles.navBtnPrimary} id="landing-register-btn">
              Get Started
              <ChevronRight size={14} />
            </Link>
          </div>
        </div>
      </nav>

      {/* ━━━━━━━━━━ HERO ━━━━━━━━━━ */}
      <section style={styles.hero} ref={heroRef} id="hero">
        <div style={styles.heroContent}>
          {/* Pill badge */}
          <div style={styles.heroBadge}>
            <SparklesIcon size={14} />
            <span>Powered by Google Gemini</span>
          </div>

          <h1 style={styles.heroTitle}>
            Understand your medical<br />
            reports <span style={styles.heroTitleAccent}>in seconds.</span>
          </h1>

          <p style={styles.heroSubtitle}>
            Upload any lab report or medical document. MediSkye's AI reads it, extracts
            key metrics, and explains everything in plain language — so you walk into
            every doctor visit fully informed.
          </p>

          <div style={styles.heroButtons} className="landing-hero-buttons">
            <Link to="/register" style={styles.heroBtnPrimary} id="hero-cta-primary">
              Start for free
              <ChevronRight size={16} />
            </Link>
            <a href="#how-it-works" style={styles.heroBtnSecondary}>
              See how it works
            </a>
          </div>
        </div>

        {/* ── Chat Mockup ── */}
        <div style={styles.mockupWrapper}>
          <div style={styles.mockupCard}>
            {/* Mockup header */}
            <div style={styles.mockupHeader}>
              <div style={styles.mockupDots}>
                <span style={{ ...styles.mockupDot, background: '#ef4444' }} />
                <span style={{ ...styles.mockupDot, background: '#f59e0b' }} />
                <span style={{ ...styles.mockupDot, background: '#22c55e' }} />
              </div>
              <span style={styles.mockupHeaderTitle}>MediSkye AI Chat</span>
              <div style={{ width: 48 }} />
            </div>

            {/* Mockup messages */}
            <div style={styles.mockupBody}>
              {/* User message */}
              <div style={styles.mockupMsgUser}>
                <div style={styles.mockupBubbleUser}>
                  What does my Hemoglobin level mean? The report says 11.2 g/dL.
                </div>
              </div>

              {/* AI response */}
              <div style={styles.mockupMsgAI}>
                <div style={styles.mockupAIAvatar}>
                  <ActivityIcon size={14} />
                </div>
                <div style={styles.mockupBubbleAI}>
                  <div style={styles.mockupAILabel}>MediSkye AI</div>
                  Your Hemoglobin is <strong style={{ color: '#f59e0b' }}>11.2 g/dL</strong>, which is
                  slightly below the normal range (12.0–16.0 g/dL for women). This may
                  indicate mild <strong>anemia</strong>. Common causes include iron
                  deficiency, vitamin B12 deficiency, or chronic conditions.
                  <div style={styles.mockupMetricChip}>
                    <span style={styles.chipDot} />
                    Hemoglobin: 11.2 g/dL — Borderline Low
                  </div>
                </div>
              </div>

              {/* Typing indicator */}
              <div style={styles.mockupMsgAI}>
                <div style={styles.mockupAIAvatar}>
                  <ActivityIcon size={14} />
                </div>
                <div style={styles.mockupTyping}>
                  <span style={styles.typingDot1} />
                  <span style={styles.typingDot2} />
                  <span style={styles.typingDot3} />
                </div>
              </div>
            </div>

            {/* Mockup input bar */}
            <div style={styles.mockupInputBar}>
              <div style={styles.mockupInput}>Ask about your report...</div>
              <div style={styles.mockupSendBtn}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="22" y1="2" x2="11" y2="13" /><polygon points="22 2 15 22 11 13 2 9 22 2" />
                </svg>
              </div>
            </div>
          </div>
          {/* Glow behind mockup */}
          <div style={styles.mockupGlow} />
        </div>
      </section>

      {/* ━━━━━━━━━━ TRUST BANNER ━━━━━━━━━━ */}
      <section style={styles.trustSection} id="trust">
        <p style={styles.trustLabel}>Built on infrastructure you trust</p>
        <div style={styles.trustLogos} className="landing-trust-logos">
          {['Google Cloud', 'Firebase', 'Neon Postgres', 'Gemini AI'].map((name) => (
            <div key={name} style={styles.trustItem}>
              <span style={styles.trustName}>{name}</span>
            </div>
          ))}
        </div>
      </section>

      {/* ━━━━━━━━━━ FEATURES ━━━━━━━━━━ */}
      <section style={styles.featuresSection} id="features">
        <div style={styles.sectionHeader}>
          <div style={styles.sectionBadge}>Features</div>
          <h2 style={styles.sectionTitle}>Everything you need to understand your health</h2>
          <p style={styles.sectionSubtitle}>
            From instant lab metric extraction to intelligent follow-up questions — MediSkye
            turns complex medical data into clear, actionable insights.
          </p>
        </div>

        <div style={styles.featuresGrid} className="landing-features-grid">
          {/* Card 1 */}
          <FeatureCard
            icon={<FlaskIcon size={24} />}
            title="Lab Metrics Dashboard"
            description="Automatically extracts biomarkers like Hemoglobin, TSH, LDL, and Vitamin D with normal range comparisons and visual status indicators."
            accent="#06b6d4"
          />
          {/* Card 2 */}
          <FeatureCard
            icon={<BrainIcon size={24} />}
            title="Remembers Your History"
            description="MediSkye remembers past conversations and previously uploaded reports — so you can ask follow-up questions weeks later without re-uploading."
            accent="#8b5cf6"
          />
          {/* Card 3 */}
          <FeatureCard
            icon={<ScanIcon size={24} />}
            title="Scans PDFs & Images"
            description="Upload PDFs, photos, or scanned lab slips. Our OCR + AI pipeline reads every format, from printed hospital reports to handwritten prescriptions."
            accent="#10b981"
          />
        </div>
      </section>

      {/* ━━━━━━━━━━ HOW IT WORKS ━━━━━━━━━━ */}
      <section style={styles.howSection} id="how-it-works">
        <div style={styles.sectionHeader}>
          <div style={styles.sectionBadge}>How it works</div>
          <h2 style={styles.sectionTitle}>Three steps to clarity</h2>
          <p style={styles.sectionSubtitle}>
            No medical degree required. Just upload, ask, and understand.
          </p>
        </div>

        <div style={styles.stepsRow} className="landing-steps-row">
          <StepCard
            number="01"
            icon={<UploadIcon size={28} />}
            title="Upload your report"
            description="Drag and drop a PDF, photo, or scanned image of your lab results. MediSkye handles any format."
          />
          <div style={styles.stepConnector} className="landing-step-connector">
            <div style={styles.stepConnectorLine} />
            <ChevronRight size={20} />
          </div>
          <StepCard
            number="02"
            icon={<SparklesIcon size={28} />}
            title="AI analyzes it"
            description="Gemini AI extracts every metric, identifies abnormal values, and prepares a clear, plain-language summary."
          />
          <div style={styles.stepConnector} className="landing-step-connector">
            <div style={styles.stepConnectorLine} />
            <ChevronRight size={20} />
          </div>
          <StepCard
            number="03"
            icon={<MessageIcon size={28} />}
            title="Ask anything"
            description="Chat with MediSkye about your results. Ask follow-ups, compare past reports, or get a doctor-visit summary."
          />
        </div>
      </section>

      {/* ━━━━━━━━━━ CTA BANNER ━━━━━━━━━━ */}
      <section style={styles.ctaSection}>
        <div style={styles.ctaGlow} />
        <h2 style={styles.ctaTitle}>Ready to understand your health?</h2>
        <p style={styles.ctaSubtitle}>
          Join thousands of patients who take charge of their medical reports with AI.
        </p>
        <Link to="/register" style={styles.ctaBtnPrimary} id="cta-register-btn">
          Get started — it's free
          <ChevronRight size={16} />
        </Link>
      </section>

      {/* ━━━━━━━━━━ FOOTER ━━━━━━━━━━ */}
      <footer style={styles.footer} id="landing-footer">
        <div style={styles.footerInner} className="landing-footer-inner">
          <div style={styles.footerBrand}>
            <div style={styles.footerLogoRow}>
              <div style={styles.navLogoBox}>
                <ActivityIcon size={16} />
              </div>
              <span style={styles.footerLogoText}>MediSkye</span>
            </div>
            <p style={styles.footerTagline}>
              AI-powered medical report analysis.
            </p>
          </div>

          <div style={styles.footerLinks}>
            <div style={styles.footerCol}>
              <h4 style={styles.footerColTitle}>Product</h4>
              <a href="#features" style={styles.footerLink}>Features</a>
              <a href="#how-it-works" style={styles.footerLink}>How it works</a>
            </div>
            <div style={styles.footerCol}>
              <h4 style={styles.footerColTitle}>Account</h4>
              <Link to="/login" style={styles.footerLink}>Sign in</Link>
              <Link to="/register" style={styles.footerLink}>Create account</Link>
            </div>
          </div>
        </div>

        <div style={styles.footerDivider} />

        <div style={styles.footerBottom}>
          <p style={styles.footerCopyright}>
            © {new Date().getFullYear()} MediSkye. All rights reserved.
          </p>
          <p style={styles.footerDisclaimer}>
            ⚕️ MediSkye is an AI assistant for informational purposes only. It does not provide
            medical diagnoses or replace professional medical advice. Always consult a qualified
            healthcare provider for clinical decisions.
          </p>
        </div>
      </footer>

      {/* Inline keyframe animations */}
      <style>{keyframes}</style>
    </div>
  );
}


/* ─── Sub-components ─── */

function FeatureCard({ icon, title, description, accent }) {
  return (
    <div style={styles.featureCard} className="landing-feature-card">
      <div style={{ ...styles.featureIconBox, background: `${accent}15`, color: accent }}>
        {icon}
      </div>
      <h3 style={styles.featureTitle}>{title}</h3>
      <p style={styles.featureDesc}>{description}</p>
    </div>
  );
}

function StepCard({ number, icon, title, description }) {
  return (
    <div style={styles.stepCard} className="landing-step-card">
      <div style={styles.stepNumber}>{number}</div>
      <div style={styles.stepIconBox}>{icon}</div>
      <h3 style={styles.stepTitle}>{title}</h3>
      <p style={styles.stepDesc}>{description}</p>
    </div>
  );
}


/* ─── Keyframe animations ─── */
const keyframes = `
  @keyframes landing-float {
    0%, 100% { transform: translateY(0); }
    50% { transform: translateY(-8px); }
  }
  @keyframes landing-pulse-glow {
    0%, 100% { opacity: 0.4; }
    50% { opacity: 0.7; }
  }
  @keyframes landing-typing {
    0%, 80%, 100% { opacity: 0.3; transform: scale(0.8); }
    40% { opacity: 1; transform: scale(1); }
  }
  @keyframes landing-fade-up {
    from { opacity: 0; transform: translateY(20px); }
    to { opacity: 1; transform: translateY(0); }
  }

  .landing-feature-card {
    transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
  }
  .landing-feature-card:hover {
    transform: translateY(-4px) !important;
    border-color: rgba(6, 182, 212, 0.3) !important;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4) !important;
  }
  .landing-step-card {
    transition: transform 0.25s ease, border-color 0.25s ease;
  }
  .landing-step-card:hover {
    transform: translateY(-3px) !important;
    border-color: rgba(6, 182, 212, 0.25) !important;
  }

  /* Smooth scroll */
  html { scroll-behavior: smooth; }

  /* Navbar hover states */
  #landing-nav a[href]:hover {
    color: #f4f4f5 !important;
  }

  /* ── Responsive: Tablet ── */
  @media (max-width: 1024px) {
    #hero {
      grid-template-columns: 1fr !important;
      gap: 48px !important;
      padding-top: 60px !important;
      text-align: center;
    }
    #hero h1 {
      font-size: 40px !important;
    }
    #hero p {
      margin-left: auto !important;
      margin-right: auto !important;
    }
    #hero > div:first-child {
      align-items: center !important;
    }
    #features .landing-features-grid {
      grid-template-columns: 1fr !important;
    }
  }

  /* ── Responsive: Mobile ── */
  @media (max-width: 768px) {
    #landing-nav > div > div:nth-child(2) {
      display: none !important;
    }
    #hero {
      padding: 40px 16px 20px !important;
    }
    #hero h1 {
      font-size: 32px !important;
    }
    #hero > div:last-child {
      max-width: 100% !important;
    }
    #features, #how-it-works {
      padding: 64px 16px !important;
    }
    .landing-steps-row {
      flex-direction: column !important;
      align-items: center !important;
      gap: 16px !important;
    }
    .landing-step-connector {
      display: none !important;
    }
    .landing-step-card {
      flex: 1 1 100% !important;
      max-width: 400px !important;
    }
    .landing-features-grid {
      grid-template-columns: 1fr !important;
    }
    .landing-trust-logos {
      gap: 24px !important;
    }
    .landing-hero-buttons {
      flex-direction: column !important;
      width: 100%;
    }
    .landing-hero-buttons a {
      width: 100% !important;
      justify-content: center !important;
      text-align: center;
    }
    .landing-footer-inner {
      flex-direction: column !important;
      gap: 32px !important;
    }
  }

  @media (max-width: 480px) {
    #hero h1 {
      font-size: 28px !important;
    }
    .landing-section-title {
      font-size: 28px !important;
    }
    .landing-cta-title {
      font-size: 28px !important;
    }
  }
`;


/* ─── Styles (inline object) ─── */
const styles = {
  // ── Page ──
  page: {
    minHeight: '100vh',
    background: '#000000',
    color: '#f4f4f5',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    position: 'relative',
    overflow: 'hidden',
  },

  // ── Background effects ──
  bgGradient: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'radial-gradient(ellipse 80% 60% at 50% -20%, rgba(6, 182, 212, 0.08), transparent 70%)',
    pointerEvents: 'none',
    zIndex: 0,
  },
  bgGrid: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    backgroundImage: `
      linear-gradient(rgba(63, 63, 70, 0.08) 1px, transparent 1px),
      linear-gradient(90deg, rgba(63, 63, 70, 0.08) 1px, transparent 1px)
    `,
    backgroundSize: '64px 64px',
    pointerEvents: 'none',
    zIndex: 0,
  },

  // ── Navbar ──
  nav: {
    position: 'sticky',
    top: 0,
    zIndex: 50,
    backdropFilter: 'blur(16px) saturate(180%)',
    WebkitBackdropFilter: 'blur(16px) saturate(180%)',
    background: 'rgba(0, 0, 0, 0.7)',
    borderBottom: '1px solid rgba(63, 63, 70, 0.3)',
  },
  navInner: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '0 24px',
    height: 64,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  navBrand: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    textDecoration: 'none',
    color: '#f4f4f5',
  },
  navLogoBox: {
    width: 32,
    height: 32,
    borderRadius: 8,
    background: '#f4f4f5',
    color: '#09090b',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  navLogoText: {
    fontSize: 17,
    fontWeight: 600,
    letterSpacing: '-0.02em',
  },
  navLinks: {
    display: 'flex',
    gap: 32,
  },
  navLink: {
    fontSize: 14,
    fontWeight: 400,
    color: '#a1a1aa',
    textDecoration: 'none',
    transition: 'color 0.15s',
  },
  navActions: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
  },
  navBtnGhost: {
    fontSize: 14,
    fontWeight: 500,
    color: '#a1a1aa',
    textDecoration: 'none',
    padding: '8px 16px',
    borderRadius: 10,
    transition: 'color 0.15s, background 0.15s',
  },
  navBtnPrimary: {
    fontSize: 14,
    fontWeight: 500,
    color: '#000',
    background: '#f4f4f5',
    textDecoration: 'none',
    padding: '8px 18px',
    borderRadius: 10,
    display: 'flex',
    alignItems: 'center',
    gap: 4,
    transition: 'background 0.15s, transform 0.1s',
  },

  // ── Hero ──
  hero: {
    position: 'relative',
    zIndex: 1,
    maxWidth: 1200,
    margin: '0 auto',
    padding: '80px 24px 40px',
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 60,
    alignItems: 'center',
  },
  heroContent: {
    display: 'flex',
    flexDirection: 'column',
    gap: 24,
    animation: 'landing-fade-up 0.6s ease-out',
  },
  heroBadge: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '6px 14px',
    borderRadius: 100,
    border: '1px solid rgba(6, 182, 212, 0.25)',
    background: 'rgba(6, 182, 212, 0.06)',
    color: '#22d3ee',
    fontSize: 13,
    fontWeight: 500,
    width: 'fit-content',
  },
  heroTitle: {
    fontSize: 52,
    fontWeight: 700,
    lineHeight: 1.1,
    letterSpacing: '-0.03em',
    color: '#fafafa',
    margin: 0,
  },
  heroTitleAccent: {
    background: 'linear-gradient(135deg, #06b6d4, #22d3ee, #67e8f9)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    backgroundClip: 'text',
  },
  heroSubtitle: {
    fontSize: 17,
    lineHeight: 1.65,
    color: '#a1a1aa',
    maxWidth: 520,
    margin: 0,
  },
  heroButtons: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    marginTop: 8,
  },
  heroBtnPrimary: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '14px 28px',
    borderRadius: 12,
    background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    color: '#fff',
    fontSize: 15,
    fontWeight: 600,
    textDecoration: 'none',
    transition: 'transform 0.15s, box-shadow 0.15s',
    boxShadow: '0 0 24px rgba(6, 182, 212, 0.25)',
  },
  heroBtnSecondary: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    padding: '14px 24px',
    borderRadius: 12,
    border: '1px solid rgba(63, 63, 70, 0.5)',
    color: '#a1a1aa',
    fontSize: 15,
    fontWeight: 500,
    textDecoration: 'none',
    transition: 'border-color 0.15s, color 0.15s',
  },

  // ── Chat Mockup ──
  mockupWrapper: {
    position: 'relative',
    animation: 'landing-fade-up 0.8s ease-out 0.15s both',
  },
  mockupCard: {
    borderRadius: 16,
    border: '1px solid rgba(63, 63, 70, 0.4)',
    background: 'rgba(9, 9, 11, 0.9)',
    backdropFilter: 'blur(12px)',
    overflow: 'hidden',
    boxShadow: '0 24px 64px rgba(0, 0, 0, 0.5)',
    animation: 'landing-float 6s ease-in-out infinite',
  },
  mockupHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: '1px solid rgba(63, 63, 70, 0.3)',
    background: 'rgba(24, 24, 27, 0.5)',
  },
  mockupDots: {
    display: 'flex',
    gap: 6,
  },
  mockupDot: {
    display: 'inline-block',
    width: 10,
    height: 10,
    borderRadius: '50%',
    opacity: 0.7,
  },
  mockupHeaderTitle: {
    fontSize: 12,
    fontWeight: 500,
    color: '#71717a',
    letterSpacing: '0.02em',
  },
  mockupBody: {
    padding: '20px 16px',
    display: 'flex',
    flexDirection: 'column',
    gap: 16,
    minHeight: 240,
  },

  // User message
  mockupMsgUser: {
    display: 'flex',
    justifyContent: 'flex-end',
  },
  mockupBubbleUser: {
    maxWidth: '80%',
    padding: '10px 14px',
    borderRadius: '14px 14px 4px 14px',
    background: 'rgba(6, 182, 212, 0.12)',
    border: '1px solid rgba(6, 182, 212, 0.2)',
    color: '#e4e4e7',
    fontSize: 13,
    lineHeight: 1.55,
  },

  // AI message
  mockupMsgAI: {
    display: 'flex',
    gap: 10,
    alignItems: 'flex-start',
  },
  mockupAIAvatar: {
    width: 28,
    height: 28,
    borderRadius: 8,
    background: '#f4f4f5',
    color: '#09090b',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 2,
  },
  mockupBubbleAI: {
    padding: '10px 14px',
    borderRadius: '14px 14px 14px 4px',
    background: 'rgba(24, 24, 27, 0.7)',
    border: '1px solid rgba(63, 63, 70, 0.3)',
    color: '#d4d4d8',
    fontSize: 13,
    lineHeight: 1.6,
    maxWidth: '90%',
  },
  mockupAILabel: {
    fontSize: 11,
    fontWeight: 600,
    color: '#06b6d4',
    marginBottom: 4,
    letterSpacing: '0.02em',
  },
  mockupMetricChip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 6,
    marginTop: 10,
    padding: '6px 12px',
    borderRadius: 8,
    background: 'rgba(245, 158, 11, 0.08)',
    border: '1px solid rgba(245, 158, 11, 0.15)',
    fontSize: 12,
    fontWeight: 500,
    color: '#fbbf24',
  },
  chipDot: {
    display: 'inline-block',
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#f59e0b',
  },

  // Typing indicator
  mockupTyping: {
    display: 'flex',
    gap: 4,
    padding: '12px 16px',
    borderRadius: '14px 14px 14px 4px',
    background: 'rgba(24, 24, 27, 0.7)',
    border: '1px solid rgba(63, 63, 70, 0.3)',
  },
  typingDot1: {
    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
    background: '#71717a', animation: 'landing-typing 1.4s infinite 0s',
  },
  typingDot2: {
    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
    background: '#71717a', animation: 'landing-typing 1.4s infinite 0.2s',
  },
  typingDot3: {
    display: 'inline-block', width: 6, height: 6, borderRadius: '50%',
    background: '#71717a', animation: 'landing-typing 1.4s infinite 0.4s',
  },

  // Mockup input bar
  mockupInputBar: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    padding: '12px 16px',
    borderTop: '1px solid rgba(63, 63, 70, 0.3)',
    background: 'rgba(24, 24, 27, 0.3)',
  },
  mockupInput: {
    flex: 1,
    padding: '10px 14px',
    borderRadius: 10,
    background: 'rgba(24, 24, 27, 0.8)',
    border: '1px solid rgba(63, 63, 70, 0.3)',
    color: '#52525b',
    fontSize: 13,
  },
  mockupSendBtn: {
    width: 36,
    height: 36,
    borderRadius: 10,
    background: '#06b6d4',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  mockupGlow: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: '120%',
    height: '120%',
    background: 'radial-gradient(circle, rgba(6, 182, 212, 0.06) 0%, transparent 60%)',
    pointerEvents: 'none',
    zIndex: -1,
    animation: 'landing-pulse-glow 4s ease-in-out infinite',
  },

  // ── Trust Banner ──
  trustSection: {
    position: 'relative',
    zIndex: 1,
    padding: '48px 24px',
    borderTop: '1px solid rgba(63, 63, 70, 0.15)',
    borderBottom: '1px solid rgba(63, 63, 70, 0.15)',
    textAlign: 'center',
  },
  trustLabel: {
    fontSize: 13,
    fontWeight: 500,
    color: '#52525b',
    letterSpacing: '0.08em',
    textTransform: 'uppercase',
    marginBottom: 24,
  },
  trustLogos: {
    display: 'flex',
    justifyContent: 'center',
    gap: 48,
    flexWrap: 'wrap',
  },
  trustItem: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  trustName: {
    fontSize: 16,
    fontWeight: 600,
    color: '#3f3f46',
    letterSpacing: '-0.01em',
  },

  // ── Features ──
  featuresSection: {
    position: 'relative',
    zIndex: 1,
    maxWidth: 1200,
    margin: '0 auto',
    padding: '96px 24px',
  },
  sectionHeader: {
    textAlign: 'center',
    marginBottom: 56,
    maxWidth: 640,
    margin: '0 auto 56px',
  },
  sectionBadge: {
    display: 'inline-flex',
    padding: '5px 14px',
    borderRadius: 100,
    border: '1px solid rgba(6, 182, 212, 0.2)',
    background: 'rgba(6, 182, 212, 0.05)',
    color: '#22d3ee',
    fontSize: 13,
    fontWeight: 500,
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 36,
    fontWeight: 700,
    letterSpacing: '-0.025em',
    color: '#fafafa',
    margin: '0 0 16px',
    lineHeight: 1.15,
  },
  sectionSubtitle: {
    fontSize: 16,
    lineHeight: 1.65,
    color: '#71717a',
    margin: 0,
  },
  featuresGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(3, 1fr)',
    gap: 24,
  },
  featureCard: {
    padding: 32,
    borderRadius: 16,
    border: '1px solid rgba(63, 63, 70, 0.3)',
    background: 'rgba(9, 9, 11, 0.6)',
    backdropFilter: 'blur(8px)',
  },
  featureIconBox: {
    width: 48,
    height: 48,
    borderRadius: 12,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 20,
  },
  featureTitle: {
    fontSize: 18,
    fontWeight: 600,
    color: '#fafafa',
    margin: '0 0 10px',
    letterSpacing: '-0.01em',
  },
  featureDesc: {
    fontSize: 14,
    lineHeight: 1.65,
    color: '#71717a',
    margin: 0,
  },

  // ── How it Works ──
  howSection: {
    position: 'relative',
    zIndex: 1,
    maxWidth: 1200,
    margin: '0 auto',
    padding: '96px 24px',
  },
  stepsRow: {
    display: 'flex',
    alignItems: 'flex-start',
    justifyContent: 'center',
    gap: 0,
  },
  stepCard: {
    flex: '0 1 300px',
    padding: 32,
    borderRadius: 16,
    border: '1px solid rgba(63, 63, 70, 0.25)',
    background: 'rgba(9, 9, 11, 0.5)',
    textAlign: 'center',
  },
  stepNumber: {
    fontSize: 40,
    fontWeight: 700,
    color: 'rgba(6, 182, 212, 0.15)',
    letterSpacing: '-0.04em',
    marginBottom: 12,
    lineHeight: 1,
  },
  stepIconBox: {
    color: '#06b6d4',
    marginBottom: 16,
    display: 'flex',
    justifyContent: 'center',
  },
  stepTitle: {
    fontSize: 18,
    fontWeight: 600,
    color: '#fafafa',
    margin: '0 0 10px',
  },
  stepDesc: {
    fontSize: 14,
    lineHeight: 1.6,
    color: '#71717a',
    margin: 0,
  },
  stepConnector: {
    display: 'flex',
    alignItems: 'center',
    gap: 0,
    color: '#3f3f46',
    paddingTop: 80,
    flexShrink: 0,
    width: 48,
    justifyContent: 'center',
  },
  stepConnectorLine: {
    width: 16,
    height: 1,
    background: 'rgba(63, 63, 70, 0.4)',
  },

  // ── CTA Section ──
  ctaSection: {
    position: 'relative',
    zIndex: 1,
    textAlign: 'center',
    padding: '96px 24px',
    overflow: 'hidden',
  },
  ctaGlow: {
    position: 'absolute',
    top: '50%',
    left: '50%',
    transform: 'translate(-50%, -50%)',
    width: 600,
    height: 300,
    background: 'radial-gradient(ellipse, rgba(6, 182, 212, 0.08), transparent 70%)',
    pointerEvents: 'none',
  },
  ctaTitle: {
    fontSize: 36,
    fontWeight: 700,
    color: '#fafafa',
    margin: '0 0 16px',
    letterSpacing: '-0.025em',
    position: 'relative',
    zIndex: 1,
  },
  ctaSubtitle: {
    fontSize: 16,
    color: '#71717a',
    margin: '0 0 32px',
    position: 'relative',
    zIndex: 1,
  },
  ctaBtnPrimary: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 8,
    padding: '16px 32px',
    borderRadius: 14,
    background: 'linear-gradient(135deg, #06b6d4, #0891b2)',
    color: '#fff',
    fontSize: 16,
    fontWeight: 600,
    textDecoration: 'none',
    boxShadow: '0 0 32px rgba(6, 182, 212, 0.3)',
    transition: 'transform 0.15s, box-shadow 0.15s',
    position: 'relative',
    zIndex: 1,
  },

  // ── Footer ──
  footer: {
    position: 'relative',
    zIndex: 1,
    borderTop: '1px solid rgba(63, 63, 70, 0.2)',
    padding: '48px 24px 32px',
  },
  footerInner: {
    maxWidth: 1200,
    margin: '0 auto',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexWrap: 'wrap',
    gap: 40,
  },
  footerBrand: {
    maxWidth: 280,
  },
  footerLogoRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 12,
  },
  footerLogoText: {
    fontSize: 16,
    fontWeight: 600,
    color: '#e4e4e7',
    letterSpacing: '-0.01em',
  },
  footerTagline: {
    fontSize: 14,
    color: '#52525b',
    margin: 0,
    lineHeight: 1.5,
  },
  footerLinks: {
    display: 'flex',
    gap: 64,
  },
  footerCol: {
    display: 'flex',
    flexDirection: 'column',
    gap: 10,
  },
  footerColTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: '#a1a1aa',
    margin: '0 0 4px',
    letterSpacing: '0.03em',
    textTransform: 'uppercase',
  },
  footerLink: {
    fontSize: 14,
    color: '#52525b',
    textDecoration: 'none',
    transition: 'color 0.15s',
  },
  footerDivider: {
    maxWidth: 1200,
    margin: '32px auto',
    height: 1,
    background: 'rgba(63, 63, 70, 0.2)',
  },
  footerBottom: {
    maxWidth: 1200,
    margin: '0 auto',
    textAlign: 'center',
  },
  footerCopyright: {
    fontSize: 13,
    color: '#3f3f46',
    margin: '0 0 12px',
  },
  footerDisclaimer: {
    fontSize: 12,
    color: '#3f3f46',
    lineHeight: 1.6,
    maxWidth: 640,
    margin: '0 auto',
  },
};
