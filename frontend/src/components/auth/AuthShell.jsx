import React from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Lock } from 'lucide-react';
import { BrandLockup, BrandMark } from '../workbench/Brand';
import RangeBar from '../clinical/RangeBar';
import StatusPill from '../clinical/StatusPill';
import DeltaIndicator from '../clinical/DeltaIndicator';

const SPECIMEN = [
  { test: 'Serum Ferritin', value: '84', unit: 'ng/mL', range: '30–400', status: 'Normal' },
  { test: 'Vitamin D (25-OH)', value: '24.0', unit: 'ng/mL', range: '30–100', status: 'Low', previous_value: '44.0', delta_pct: -45.5 },
  { test: 'LDL Cholesterol', value: '162', unit: 'mg/dL', range: '<100', status: 'High', previous_value: '148', delta_pct: 9.5 },
];

/**
 * Split auth layout: product context on the left (≥1024px), form on the right.
 * Children are the existing Login / Register form contents, unchanged.
 */
export default function AuthShell({ children }) {
  return (
    <div className="relative min-h-app w-full overflow-hidden bg-obsidian font-sans lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(440px,1fr)] lg:items-stretch">
      <aside data-testid="auth-brand-panel" className="hidden lg:flex relative flex-col justify-between overflow-hidden border-r border-white/[0.06] px-12 py-10 bg-ambient">
        <Link to="/" aria-label="MediSkye home" className="relative z-[1] w-fit">
          <BrandLockup size={32} />
        </Link>

        <div className="relative z-[1] max-w-[460px]">
          <p className="ms-display text-[40px] leading-[1.05] text-white mb-4">Every value, placed in context.</p>
          <p className="text-[15px] leading-relaxed text-ink-mute mb-8">
            MediSkye reads your lab report, shows where each biomarker sits in its reference interval, and tracks how it moved since your last test.
          </p>

          <div className="rounded-3xl ms-glass p-5 space-y-4" aria-hidden="true">
            <div className="flex items-center justify-between text-xs text-ink-faint">
              <span>Follow-up panel, 04 Nov 2026</span>
              <span className="ms-num">3 of 24 shown</span>
            </div>
            {SPECIMEN.map((row) => (
              <div key={row.test} className="space-y-1.5">
                <div className="flex items-center justify-between gap-3">
                  <span className="text-[13px] font-medium text-white">{row.test}</span>
                  <StatusPill row={row} size="sm" />
                </div>
                <div className="flex items-baseline justify-between gap-3">
                  <span className="ms-num text-lg text-white">
                    {row.value} <span className="text-xs text-ink-mute">{row.unit}</span>
                  </span>
                  {row.previous_value ? <DeltaIndicator row={row} compact showValues={false} /> : <span className="ms-num text-xs text-ink-faint">ref {row.range}</span>}
                </div>
                <RangeBar row={row} size="sm" />
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-[1] flex items-center gap-5 text-xs text-ink-faint">
          <span className="inline-flex items-center gap-1.5"><Lock className="w-3.5 h-3.5" /> Fernet encryption at rest, TLS 1.3 in transit</span>
          <span className="inline-flex items-center gap-1.5"><ShieldCheck className="w-3.5 h-3.5" /> Never used to train public models</span>
        </div>
      </aside>

      <main className="relative flex items-center justify-center min-h-app px-0 sm:px-6 py-8 lg:py-10">
        <div className="login-bg-glow lg:hidden" />
        <div className="w-full flex flex-col items-center">
          <Link to="/" aria-label="MediSkye home" className="lg:hidden mb-2 self-start sm:self-center px-5 sm:px-0">
            <BrandMark size={34} />
          </Link>
          {children}
        </div>
      </main>
    </div>
  );
}
