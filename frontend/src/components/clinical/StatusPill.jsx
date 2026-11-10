import React from 'react';
import { cn } from '../../lib/cn';
import { classifyStatus, TONE } from '../../lib/clinical';

/**
 * Accessible status pill. Direction is carried by a glyph AND text, never
 * by color alone:  ↑ High · ↓ Low · ▲ Critical · ↘ Notable Drop · ✓ Normal
 */
export default function StatusPill({ row, size = 'md', className }) {
  const c = classifyStatus(row);
  const deltaAlert = row?.delta_alert;
  const sizes = { sm: 'text-[10px] px-2 py-0.5', md: 'text-[11px] px-2.5 py-0.5' };

  let tone = 'neutral';
  let glyph = null;
  let label = String(row?.status || '').trim();

  if (c === 'critical') {
    tone = 'rose';
    glyph = '▲';
    label = label || 'Critical';
  } else if (c === 'high') {
    tone = 'rose';
    glyph = '↑';
    label = label || 'High';
  } else if (c === 'low') {
    tone = 'amber';
    glyph = '↓';
    label = label || 'Low';
  } else if (deltaAlert) {
    tone = 'amber';
    glyph = /drop|decreas|fall/i.test(deltaAlert) ? '↘' : '↗';
    label = deltaAlert;
  } else if (c === 'borderline') {
    tone = 'amber';
    glyph = '~';
    label = label || 'Borderline';
  } else if (c === 'normal') {
    tone = 'emerald';
    glyph = '✓';
    label = label || 'Normal';
  } else if (c === 'unknown') {
    tone = 'neutral';
    glyph = null;
    label = label || 'Unknown';
  }

  const t = TONE[tone];
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border font-semibold whitespace-nowrap',
        sizes[size],
        t.bg,
        t.text,
        t.border,
        className
      )}
    >
      {glyph ? `${glyph} ${label}` : label}
    </span>
  );
}
