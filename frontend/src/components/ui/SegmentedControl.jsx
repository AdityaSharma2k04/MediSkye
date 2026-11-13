import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../../lib/cn';

/**
 * Pill segmented control with a sliding active indicator.
 * options: [{ value, label, icon?: Component, ariaLabel?, onSelect? }]
 */
export default function SegmentedControl({ options, value, onChange, layoutId, size = 'md', className, fullWidth = false }) {
  const heights = { sm: 'h-8 text-xs', md: 'h-9 text-[13px]' };
  return (
    <div
      role="tablist"
      className={cn(
        'relative inline-flex items-center rounded-full p-1 bg-white/[0.035] border border-white/[0.07]',
        fullWidth && 'flex w-full',
        className
      )}
    >
      {options.map((opt) => {
        const isActive = opt.value === value;
        const Icon = opt.icon;
        return (
          <button
            key={opt.value}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-label={opt.ariaLabel || undefined}
            onClick={() => (opt.onSelect ? opt.onSelect() : onChange?.(opt.value))}
            className={cn(
              'relative z-[1] inline-flex items-center justify-center gap-1.5 px-3 rounded-full font-medium transition-colors',
              heights[size],
              fullWidth && 'flex-1',
              isActive ? 'text-white' : 'text-ink-mute hover:text-ink'
            )}
          >
            {isActive && (
              <motion.span
                layoutId={layoutId}
                className="absolute inset-0 -z-[1] rounded-full bg-white/[0.09] border border-white/[0.1] shadow-specular"
                transition={{ type: 'spring', stiffness: 520, damping: 38 }}
              />
            )}
            {Icon && <Icon className="w-3.5 h-3.5" aria-hidden="true" />}
            <span>{opt.label}</span>
            {opt.count !== undefined && opt.count !== null && (
              <span className={cn('ms-num text-xs px-1.5 rounded-full', isActive ? 'bg-white/10 text-white' : 'bg-white/[0.05] text-ink-mute')}>
                {opt.count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}
