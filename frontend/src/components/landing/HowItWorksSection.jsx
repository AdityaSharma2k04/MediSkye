import React from 'react';
import {
  C,
  SERIF,
  fit,
  UploadIcon,
  SparklesIcon,
  ActivityIcon,
  sharedStyles,
} from './shared';

const METRICS = [
  { name: 'Hemoglobin', value: '11.2 g/dL', status: 'Borderline low', color: C.amber },
  { name: 'TSH', value: '2.1 mIU/L', status: 'Normal', color: C.green },
  { name: 'LDL', value: '142 mg/dL', status: 'High', color: C.red },
];

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

function StepCard({ number, visual, title, description }) {
  return (
    <div
      className="landing-step-card group transform-gpu will-change-transform bg-carbon border border-white/10 rounded-2xl p-8 transition-all duration-300 ease-in-out hover:-translate-y-1.5 hover:scale-[1.02] hover:shadow-xl hover:shadow-cyan-500/10 hover:border-cyan-500/30 cursor-default"
    >
      {visual}
      <div style={styles.stepNumber}>{number}</div>
      <h3 style={styles.stepTitle}>{title}</h3>
      <p style={styles.stepDesc}>{description}</p>
    </div>
  );
}

export default function HowItWorksSection() {
  return (
    <section style={styles.howSection}>
      <div style={styles.howInner}>
        <p style={sharedStyles.eyebrow}>How it works</p>
        <h2 style={sharedStyles.sectionTitle}>Three steps to clarity</h2>
        <p style={{ ...sharedStyles.sectionSubtitle, marginBottom: 48 }}>
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
  );
}

const styles = {
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
  stepNumber: {
    fontFamily: SERIF,
    fontSize: 56,
    lineHeight: 1,
    color: C.cyan,
    marginBottom: 12,
  },
  stepTitle: { fontSize: 19, fontWeight: 600, color: C.heading, margin: '0 0 8px' },
  stepDesc: { fontSize: 16, color: C.muted, margin: 0 },

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
};
