import React from 'react';
import { cn } from '../../lib/cn';
import { deltaPct, formatDeltaPct, isNotableShift } from '../../lib/clinical';

/**
 * Baseline → follow-up readout:  44.0 → 24.0 ng/mL  ↓ 45.5%
 * Amber when |Δ| ≥ 10% (or backend delta_alert), muted otherwise.
 */
export default function DeltaIndicator({ row, compact = false, showValues = true, className }) {
  const d = deltaPct(row);
  const hasPrev = row?.previous_value !== null && row?.previous_value !== undefined && row?.previous_value !== '';
  if (!hasPrev && d === null) return null;

  const notable = isNotableShift(row);
  const arrow = d === null ? '' : d < 0 ? '↓' : d > 0 ? '↑' : '→';
  const pct = d === null ? '' : formatDeltaPct(Math.abs(d)).replace('+', '');

  return (
    <span className={cn('inline-flex items-baseline gap-1.5 ms-num whitespace-nowrap text-xs', className)}>
      {showValues && hasPrev && (
        <span className="text-ink-mute">
          {row.previous_value} <span className="text-ink-faint">→</span> <span className="text-ink-soft">{row.value}</span>
          {row.unit && !compact ? <span className="text-ink-faint"> {row.unit}</span> : null}
        </span>
      )}
      {d !== null && (
        <span className={cn('font-semibold', notable ? 'text-amber-700' : 'text-ink-mute')}>
          {arrow} {pct}
        </span>
      )}
    </span>
  );
}
