import React from 'react';
import { Link } from 'react-router-dom';
import { C, sharedStyles } from './shared';

export default function CTASection() {
  return (
    <section style={styles.ctaSection}>
      <div style={styles.ctaCard}>
        <h2 style={{ ...sharedStyles.sectionTitle, margin: '0 auto 12px', maxWidth: 620 }}>
          Ready to understand your health?
        </h2>
        <p style={styles.ctaSubtitle}>
          Upload your first report and see it explained in plain language.
        </p>
        <Link
          to="/register"
          style={sharedStyles.btnPrimary}
          className="landing-btn-primary"
          id="cta-register-btn"
        >
          Get started, it’s free
        </Link>
      </div>
    </section>
  );
}

const styles = {
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
};
