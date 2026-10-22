import React from 'react';
import { useTranslation } from 'react-i18next';
import { C, fit, sharedStyles } from './shared';

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

function ListCard({ title, color, items, isAllowed }) {
  return (
    <div
      className="landing-list-card group transform-gpu will-change-transform bg-[#0f1115] border border-white/10 rounded-2xl p-6 transition-all duration-300 ease-in-out hover:-translate-y-1.5 hover:scale-[1.02] hover:shadow-xl hover:shadow-cyan-500/10 hover:border-cyan-500/30 cursor-default"
    >
      <h3 style={{ ...styles.listCardTitle, color }} className="transition-colors duration-300">
        {title}
      </h3>
      <ul style={styles.list}>
        {items.map((item) => (
          <li key={item} style={styles.listItem} className="transition-colors duration-200 group-hover:text-zinc-100">
            <span
              style={{ color, marginRight: 10, fontWeight: 700, display: 'inline-block' }}
              className="transition-transform duration-200 group-hover:scale-110"
            >
              {isAllowed ? '✓' : '✕'}
            </span>
            <span>{item}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export default function SafetySection() {
  const { t } = useTranslation();

  return (
    <section style={styles.safetySection}>
      <div>
        <p style={sharedStyles.eyebrow}>Safety</p>
        <h2 style={sharedStyles.sectionTitle}>Built to inform, not to diagnose</h2>
        <p style={{ ...sharedStyles.sectionSubtitle, margin: 0 }}>
          MediSkye is an AI assistant for informational purposes. It helps you understand
          your results and prepare better questions. Your doctor makes the clinical decisions.
        </p>
      </div>

      <div style={styles.safetyCards}>
        <ListCard
          title={t('landing.safety_can_title', 'MediSkye can')}
          color={C.cyanText}
          items={CAN}
          isAllowed={true}
        />
        <ListCard
          title={t('landing.safety_cannot_title', 'MediSkye cannot')}
          color={C.red}
          items={CANNOT}
          isAllowed={false}
        />
      </div>
    </section>
  );
}

const styles = {
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
  listCardTitle: { fontSize: 16, fontWeight: 600, margin: '0 0 12px' },
  list: { listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: 10 },
  listItem: { color: C.body, fontSize: 15, display: 'flex', alignItems: 'flex-start' },
};
