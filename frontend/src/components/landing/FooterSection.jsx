import React from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { C, ActivityIcon, sharedStyles } from './shared';

export default function FooterSection() {
  const { t } = useTranslation();

  return (
    <footer style={styles.footer}>
      <div style={styles.footerInner}>
        <div style={styles.footerTop}>
          <div style={styles.footerBrand}>
            <div style={styles.footerLogoRow}>
              <div style={{ ...sharedStyles.logoBox, width: 28, height: 28, borderRadius: 7 }}>
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
              <h4 style={styles.footerColTitle}>Legal & Account</h4>
              <Link to="/privacy" style={styles.footerLink} className="landing-link">
                Privacy policy
              </Link>
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
  );
}

const styles = {
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
