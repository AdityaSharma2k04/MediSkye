import React from 'react';
import {
  C,
  fit,
  sharedStyles,
  FlaskIcon,
  BrainIcon,
  ScanIcon,
  ActivityIcon,
} from './shared';

function MetricsDashboardVisual() {
  return (
    <div style={styles.visual} aria-hidden="true">
      <div style={styles.extractHeader}>
        <ActivityIcon size={14} />
        <span>Live Biomarker Extraction</span>
      </div>
      <div style={styles.metricList}>
        <div style={styles.metricRow}>
          <div style={styles.metricLeft}>
            <span style={styles.metricDot(C.green)} />
            <span style={styles.metricName}>Hemoglobin</span>
            <span style={styles.metricVal}>14.5 g/dL</span>
          </div>
          <span style={styles.badge(C.green, 'rgba(52, 211, 153, 0.14)', 'rgba(52, 211, 153, 0.35)')}>
            Normal
          </span>
        </div>
        <div style={styles.metricRow}>
          <div style={styles.metricLeft}>
            <span style={styles.metricDot(C.red)} />
            <span style={styles.metricName}>LDL</span>
            <span style={styles.metricVal}>142 mg/dL</span>
          </div>
          <span style={styles.badge(C.red, 'rgba(248, 113, 113, 0.14)', 'rgba(248, 113, 113, 0.35)')}>
            High
          </span>
        </div>
      </div>
    </div>
  );
}

function HistoryVisual() {
  return (
    <div style={{ ...styles.visual, justifyContent: 'center', gap: 8 }} aria-hidden="true">
      <div style={styles.historyUserBubble}>
        What was my Vitamin D last time?
      </div>
      <div style={styles.historyAiRow}>
        <div style={styles.historyAvatar}>
          <ActivityIcon size={12} />
        </div>
        <div style={styles.historyAiBubble}>
          It was <span style={{ color: C.amber, fontWeight: 600 }}>12.0 ng/mL</span>.
        </div>
      </div>
    </div>
  );
}

function ScanVisual() {
  return (
    <div style={{ ...styles.visual, justifyContent: 'center' }} aria-hidden="true">
      <div style={styles.scanDoc}>
        <div style={styles.scanDocHeader}>
          <div style={styles.pdfBadge}>PDF</div>
          <span style={styles.scanDocName}>blood_test.pdf</span>
          <span style={styles.ocrTag}>OCR READY</span>
        </div>

        <div style={styles.scanBody}>
          <div style={styles.scanRow}>
            <span style={styles.scanTermBox}>PATIENT REPORT</span>
            <span style={styles.scanLineShort} />
          </div>
          <div style={styles.scanRow}>
            <span style={styles.scanTermActive}>
              <span style={styles.pulseDot} />
              GLUCOSE: 95 mg/dL
            </span>
            <span style={styles.scanTermBox}>NORMAL</span>
          </div>
          <div style={styles.scanRow}>
            <span style={styles.scanLineLong} />
            <span style={styles.scanTermBox}>VERIFIED</span>
          </div>
        </div>

        <div style={styles.scanBeam} />
      </div>
    </div>
  );
}

const FEATURES = [
  {
    icon: <FlaskIcon size={22} />,
    visual: <MetricsDashboardVisual />,
    title: 'Lab metrics dashboard',
    description:
      'Automatically extracts biomarkers like Hemoglobin, TSH, LDL, and Vitamin D, with normal range comparisons and clear clinical status indicators.',
  },
  {
    icon: <BrainIcon size={22} />,
    visual: <HistoryVisual />,
    title: 'Remembers your history',
    description:
      'MediSkye securely recalls past conversations and uploaded reports, so you can ask follow-up questions weeks later without re-uploading.',
  },
  {
    icon: <ScanIcon size={22} />,
    visual: <ScanVisual />,
    title: 'Scans PDFs and images',
    description:
      'Upload PDFs, camera photos, or scanned lab slips. Our high-fidelity OCR reads printed hospital reports as well as clinic prescriptions.',
  },
];

function FeatureCard({ icon, visual, title, description }) {
  return (
    <div
      style={{ display: 'flex', flexDirection: 'column' }}
      className="landing-feature-card group transform-gpu will-change-transform bg-[#0f1115] border border-white/10 rounded-2xl p-8 transition-all duration-300 ease-in-out hover:-translate-y-1.5 hover:scale-[1.02] hover:shadow-xl hover:shadow-cyan-500/10 hover:border-cyan-500/30 cursor-default"
    >
      {visual}
      <div style={styles.featureIconBox}>{icon}</div>
      <h3 style={styles.featureTitle}>{title}</h3>
      <p style={styles.featureDesc}>{description}</p>
    </div>
  );
}

export default function FeaturesSection() {
  return (
    <section style={styles.featuresSection}>
      <p style={sharedStyles.eyebrow}>Features</p>
      <h2 style={{ ...sharedStyles.sectionTitle, maxWidth: 680 }}>
        Everything you need to understand your health
      </h2>
      <p style={{ ...sharedStyles.sectionSubtitle, maxWidth: 600, marginBottom: 48 }}>
        From instant lab metric extraction to intelligent follow-up questions, MediSkye
        turns complex medical reports into clear, actionable insight.
      </p>

      <div style={styles.featuresGrid}>
        {FEATURES.map((f) => (
          <FeatureCard key={f.title} {...f} />
        ))}
      </div>
    </section>
  );
}

const styles = {
  featuresSection: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '40px 24px 96px',
  },
  featuresGrid: {
    display: 'grid',
    gridTemplateColumns: fit(260),
    gap: 24,
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
  featureDesc: { fontSize: 16, color: C.muted, margin: 0, lineHeight: 1.6 },

  // Visual Box (matches HowItWorks)
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
    justifyContent: 'center',
    gap: 10,
    position: 'relative',
    overflow: 'hidden',
  },
  extractHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 12,
    fontWeight: 600,
    color: C.cyanText,
    marginBottom: 2,
  },
  metricList: {
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  metricRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 8,
    padding: '6px 10px',
    borderRadius: 8,
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    fontSize: 12,
    color: C.body,
  },
  metricLeft: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  metricDot: (color) => ({
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: color,
  }),
  metricName: {
    fontWeight: 500,
    color: C.heading,
  },
  metricVal: {
    color: C.muted,
  },
  badge: (color, bg, border) => ({
    color,
    background: bg,
    border: `1px solid ${border}`,
    padding: '2px 8px',
    borderRadius: 6,
    fontSize: 11,
    fontWeight: 600,
  }),

  // History Visual
  historyUserBubble: {
    alignSelf: 'flex-end',
    maxWidth: '90%',
    padding: '7px 12px',
    borderRadius: '12px 12px 4px 12px',
    background: 'rgba(6, 182, 212, 0.12)',
    border: '1px solid rgba(6, 182, 212, 0.25)',
    fontSize: 12,
    color: '#e4e4e7',
  },
  historyAiRow: {
    display: 'flex',
    gap: 8,
    alignItems: 'flex-start',
  },
  historyAvatar: {
    width: 22,
    height: 22,
    borderRadius: 6,
    background: '#fafafa',
    color: C.obsidian,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    marginTop: 2,
  },
  historyAiBubble: {
    padding: '7px 12px',
    borderRadius: '12px 12px 12px 4px',
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    fontSize: 12,
    color: C.body,
  },

  // Scan Visual
  scanDoc: {
    height: '100%',
    width: '100%',
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    padding: '8px 10px',
    borderRadius: 8,
    background: C.obsidianLight,
    border: `1px solid ${C.border}`,
    boxSizing: 'border-box',
    position: 'relative',
    overflow: 'hidden',
  },
  scanDocHeader: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    paddingBottom: 6,
    borderBottom: `1px solid ${C.border}`,
  },
  pdfBadge: {
    padding: '1px 5px',
    borderRadius: 4,
    background: 'rgba(239, 68, 68, 0.2)',
    border: '1px solid rgba(239, 68, 68, 0.4)',
    color: '#f87171',
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: '0.05em',
  },
  scanDocName: {
    fontSize: 11,
    color: C.body,
    fontWeight: 500,
    flex: 1,
    overflow: 'hidden',
    textOverflow: 'ellipsis',
    whiteSpace: 'nowrap',
  },
  ocrTag: {
    fontSize: 9,
    fontWeight: 700,
    color: C.cyanText,
    letterSpacing: '0.06em',
  },
  scanBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    paddingTop: 4,
  },
  scanRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
  },
  scanTermBox: {
    padding: '2px 6px',
    borderRadius: 4,
    border: '1px dashed rgba(255, 255, 255, 0.18)',
    fontSize: 10,
    color: C.muted,
  },
  scanTermActive: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    padding: '2px 8px',
    borderRadius: 4,
    background: 'rgba(6, 182, 212, 0.14)',
    border: '1px solid rgba(6, 182, 212, 0.4)',
    color: C.cyanText,
    fontSize: 10.5,
    fontWeight: 600,
  },
  pulseDot: {
    width: 5,
    height: 5,
    borderRadius: '50%',
    background: C.cyan,
  },
  scanLineShort: {
    flex: 1,
    height: 6,
    borderRadius: 3,
    background: 'rgba(255, 255, 255, 0.08)',
  },
  scanLineLong: {
    width: 60,
    height: 6,
    borderRadius: 3,
    background: 'rgba(255, 255, 255, 0.08)',
  },
  scanBeam: {
    position: 'absolute',
    left: 0,
    right: 0,
    top: '48%',
    height: 2,
    background: 'linear-gradient(90deg, transparent 0%, rgba(6, 182, 212, 0.8) 50%, transparent 100%)',
    boxShadow: '0 0 10px rgba(6, 182, 212, 0.8)',
    pointerEvents: 'none',
  },
};
