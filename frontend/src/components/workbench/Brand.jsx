import React from 'react';
import { cn } from '../../lib/cn';

/**
 * MediSkye mark: an ECG trace crossing a reference band — the same visual
 * language as the range bars used throughout the product.
 */
export function BrandMark({ size = 28, className }) {
  const borderRadius = Math.round(size * 0.26);
  return (
    <span
      className={cn('inline-flex items-center justify-center shrink-0 relative overflow-hidden', className)}
      style={{
        width: size,
        height: size,
        borderRadius,
        background: 'linear-gradient(180deg, #22d3ee 0%, #0891b2 45%, #0284c7 100%)',
        boxShadow: '0 0 16px -2px rgba(6, 182, 212, 0.55), inset 0 0 0 1.5px rgba(165, 243, 252, 0.65)',
        border: '1px solid rgba(103, 232, 249, 0.75)',
      }}
      aria-hidden="true"
    >
      <svg width={size * 0.64} height={size * 0.64} viewBox="0 0 512 512" fill="none">
        <path
          d="M 148 264 L 210 264 L 238 176 L 282 344 L 312 264 L 364 264"
          stroke="#060A12"
          strokeWidth="42"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
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
