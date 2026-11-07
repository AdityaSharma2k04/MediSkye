import React from 'react';
import { cn } from '../../lib/cn';
import { rangeGeometry, parseNumeric, statusTone, TONE, metricName, describePlacement } from '../../lib/clinical';

/**
 * Reference-interval bar.
 *
 *   ░░░░░░▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░
 *          ◉ current   ○ previous
 *
 * The emerald band is the reference interval; the marker is the patient's
 * value colored by clinical tone. When a previous value exists, a hollow
 * ring + connecting stroke show the direction of change.
 *
 * Uses role="img" with a full sentence label (not role="progressbar" — this
 * is a position, not progress).
 */
export default function RangeBar({ row, size = 'md', showScale = false, showPrevious = true, className }) {
  const geo = rangeGeometry(row);
  if (!geo) {
    return (
      <div className={cn('text-[11px] text-ink-faint italic', className)} aria-hidden="true">
        No numeric interval
      </div>
    );
  }

  const tone = TONE[statusTone(row)] || TONE.neutral;
  const prevVal = showPrevious ? parseNumeric(row?.previous_value) : null;
  const prevGeo = prevVal !== null ? rangeGeometry(row, prevVal) : null;

  const trackH = size === 'sm' ? 'h-1.5' : 'h-2';
  const markerSize = size === 'sm' ? 'w-2.5 h-2.5' : 'w-3.5 h-3.5';
  const placement = describePlacement(row);
  const label = `${metricName(row)} ${row?.value ?? ''} ${row?.unit || ''}. ${placement || ''}${
    prevGeo ? `. Previously ${row.previous_value}.` : ''
  }`.replace(/\s+/g, ' ');

  const segLeft = prevGeo ? Math.min(prevGeo.valuePct, geo.valuePct) : 0;
  const segWidth = prevGeo ? Math.abs(geo.valuePct - prevGeo.valuePct) : 0;

  return (
    <div className={cn('w-full', className)}>
      <div role="img" aria-label={label} data-testid="range-bar" className={cn('relative w-full', size === 'sm' ? 'py-1' : 'py-1.5')}>
        <div className={cn('relative w-full rounded-full bg-white/[0.06] overflow-hidden', trackH)}>
          {/* Out-of-range shading */}
          <div className="absolute inset-y-0 left-0 bg-amber-500/[0.10]" style={{ width: `${geo.lowPct}%` }} />
          <div className="absolute inset-y-0 right-0 bg-rose-500/[0.10]" style={{ width: `${100 - geo.highPct}%` }} />
          {/* Reference interval */}
          <div
            className="absolute inset-y-0 bg-emerald-400/35 border-x border-emerald-300/60"
            style={{ left: `${geo.lowPct}%`, width: `${Math.max(0.5, geo.highPct - geo.lowPct)}%` }}
          />
          {/* Change segment */}
          {prevGeo && segWidth > 0.5 && (
            <div className="absolute inset-y-0 opacity-60" style={{ left: `${segLeft}%`, width: `${segWidth}%`, background: tone.hex }} />
          )}
        </div>

        {prevGeo && (
          <span
            aria-hidden="true"
            className={cn('absolute top-1/2 rounded-full border-2 bg-obsidian', size === 'sm' ? 'w-2 h-2' : 'w-2.5 h-2.5')}
            style={{ left: `${prevGeo.valuePct}%`, transform: 'translate(-50%, -50%)', borderColor: 'rgba(148,163,184,0.7)' }}
          />
        )}
        <span
          aria-hidden="true"
          className={cn('ms-marker-in absolute top-1/2 rounded-full ring-2 ring-obsidian', markerSize)}
          style={{ left: `${geo.valuePct}%`, transform: 'translate(-50%, -50%)', background: tone.hex, boxShadow: `0 0 12px ${tone.hex}88` }}
        />
      </div>

      {showScale && (
        <div className="relative h-4 mt-0.5 text-[10px] ms-num text-ink-faint" aria-hidden="true">
          {geo.low !== null && (
            <span className="absolute -translate-x-1/2" style={{ left: `${geo.lowPct}%` }}>
              {geo.low}
            </span>
          )}
          {geo.high !== null && (
            <span className="absolute -translate-x-1/2" style={{ left: `${geo.highPct}%` }}>
              {geo.high}
            </span>
          )}
        </div>
      )}
    </div>
  );
}
