import React from 'react';
import { cn } from '../../lib/cn';

/**
 * MediSkye mark: an ECG trace crossing a reference band — the same visual
 * language as the range bars used throughout the product.
 */
export function BrandMark({ size = 28, className }) {
  return (
    <span
      className={cn('inline-flex items-center justify-center rounded-[10px] shrink-0', className)}
      style={{
        width: size,
        height: size,
        background: 'linear-gradient(150deg, #0e7490 0%, #06b6d4 70%)',
        boxShadow: '0 0 0 1px rgba(103,232,249,0.28), 0 6px 18px -6px rgba(6,182,212,0.65), inset 0 1px 0 rgba(255,255,255,0.25)',
      }}
      aria-hidden="true"
    >
      <svg width={size * 0.62} height={size * 0.62} viewBox="0 0 24 24" fill="none">
        <rect x="2" y="9.5" width="20" height="5" rx="2.5" fill="rgba(3,16,22,0.22)" />
        <path d="M2.5 13h4l2.2-6 4.6 11 2.4-5h5.8" stroke="#031016" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

export function BrandLockup({ size = 28, className, subtitle }) {
  return (
    <span className={cn('inline-flex items-center gap-2.5 min-w-0', className)}>
      <BrandMark size={size} />
      <span className="min-w-0 leading-none">
        <span className="block text-[15px] font-semibold tracking-tight text-white">MediSkye</span>
        {subtitle && <span className="block text-xs text-ink-faint mt-1 truncate">{subtitle}</span>}
      </span>
    </span>
  );
}
