import React, { useEffect, useMemo, useRef, useState } from 'react';
import { parseRange, formatShortDate, formatNumber, TONE } from '../../lib/clinical';
import { cn } from '../../lib/cn';

/**
 * Dependency-free SVG longitudinal chart.
 *  • emerald band = reference interval
 *  • line + points = readings over time (dashed hollow point = baseline
 *    reconstructed from previous_value)
 *  • hover / focus a point to read its exact value and date
 */
export default function TrendChart({ series, height = 200, className }) {
  const [active, setActive] = useState(null);
  const wrapRef = useRef(null);
  const [W, setW] = useState(560);
  const H = height;

  // Render at the container's real pixel width so labels never scale down
  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver((entries) => {
      const w = Math.round(entries[0]?.contentRect?.width || 0);
      if (w > 0) setW(w);
    });
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const pad = { l: 44, r: 16, t: 14, b: 26 };

  const model = useMemo(() => {
    const rawPts = series?.points || [];
    if (!rawPts.length) return null;

    // Deduplicate identical (t, value) pairs
    const pts = [];
    const seen = new Set();
    for (const p of rawPts) {
      const k = `${p.t}:${p.value}`;
      if (!seen.has(k)) {
        seen.add(k);
        pts.push(p);
      }
    }
    if (!pts.length) return null;
    const range = parseRange(series.range);
    const values = pts.map((p) => p.value);
    let min = Math.min(...values);
    let max = Math.max(...values);
    // Keep at least one reference edge on-canvas so the band is always interpretable
    if (range) {
      const lo = range.low ?? range.high;
      const hi = range.high ?? range.low;
      min = Math.min(min, lo);
      max = Math.max(max, hi);
    }
    if (min === max) {
      min -= Math.abs(min) * 0.2 || 1;
      max += Math.abs(max) * 0.2 || 1;
    }
    const span = max - min;
    min -= span * 0.12;
    max += span * 0.12;
    if (min < 0 && Math.min(...values) >= 0) min = 0;

    const ts = pts.map((p) => p.t);
    const tMin = Math.min(...ts);
    const tMax = Math.max(...ts);
    const x = (t) => (tMax === tMin ? (pad.l + W - pad.r) / 2 : pad.l + ((t - tMin) / (tMax - tMin)) * (W - pad.l - pad.r));
    const y = (v) => pad.t + (1 - (v - min) / (max - min)) * (H - pad.t - pad.b);

    const coords = pts
      .map((p) => ({ ...p, cx: x(p.t), cy: y(p.value) }))
      .filter((c) => Number.isFinite(c.cx) && Number.isFinite(c.cy));
    const ticks = [0, 0.5, 1].map((f) => min + (max - min) * f);
    const band = range
      ? { y1: y(range.high ?? max), y2: y(range.low ?? min) }
      : null;
    return { coords, ticks, band, y, range };
  }, [series, H, W]);

  if (!model) return null;
  const { coords, ticks, band, y, range } = model;
  const path = coords.map((c, i) => `${i ? 'L' : 'M'}${c.cx.toFixed(1)},${c.cy.toFixed(1)}`).join(' ');
  const last = coords[coords.length - 1];
  const outOfRange = (v) => range && ((range.high !== null && v > range.high) || (range.low !== null && v < range.low));
  const pointColor = (v) => (outOfRange(v) ? (range.high !== null && v > range.high ? TONE.rose.hex : TONE.amber.hex) : TONE.emerald.hex);
  const activePt = active !== null ? coords[active] : null;

  return (
    <div ref={wrapRef} data-testid="trend-chart" className={cn('relative w-full', className)}>
      <svg width={W} height={H} viewBox={`0 0 ${W} ${H}`} className="block w-full" role="img" aria-label={`${series.name} trend across ${coords.length} readings`}>
        {band && (
          <rect x={pad.l} width={W - pad.l - pad.r} y={Math.min(band.y1, band.y2)} height={Math.abs(band.y2 - band.y1)} fill="rgba(16,185,129,0.09)" />
        )}
        {band && range.high !== null && <line x1={pad.l} x2={W - pad.r} y1={band.y1} y2={band.y1} stroke="rgba(16,185,129,0.35)" strokeDasharray="3 4" />}
        {band && range.low !== null && <line x1={pad.l} x2={W - pad.r} y1={band.y2} y2={band.y2} stroke="rgba(16,185,129,0.35)" strokeDasharray="3 4" />}

        {ticks.map((tv, i) => (
          <g key={i}>
            <line x1={pad.l} x2={W - pad.r} y1={y(tv)} y2={y(tv)} stroke="rgba(255,255,255,0.04)" />
            <text x={pad.l - 8} y={y(tv) + 3} textAnchor="end" fontSize="10" fill="#5d6a7c" fontFamily="JetBrains Mono Variable, monospace">
              {formatNumber(tv)}
            </text>
          </g>
        ))}

        <path d={path} fill="none" stroke="#67e8f9" strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

        {coords.map((c, i) => (
          <g key={`${c.t}-${i}`}>
            <circle
              cx={c.cx}
              cy={c.cy}
              r={active === i ? 7 : 5}
              fill={c.synthetic ? '#05070b' : pointColor(c.value)}
              stroke={c.synthetic ? '#94a3b8' : '#05070b'}
              strokeWidth={c.synthetic ? 1.75 : 2}
              strokeDasharray={c.synthetic ? '2 2' : undefined}
              tabIndex={0}
              role="button"
              aria-label={`${formatNumber(c.value)} ${series.unit || ''} on ${c.label || formatShortDate(c.t)}`}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(i)}
              onBlur={() => setActive(null)}
              style={{ cursor: 'pointer', outline: 'none', transition: 'r 120ms ease' }}
            />
            <text x={c.cx} y={H - 8} textAnchor="middle" fontSize="10" fill="#5d6a7c">
              {c.t > 1e11 ? new Date(c.t).toLocaleDateString('en-GB', { month: 'short', year: '2-digit' }) : `#${i + 1}`}
            </text>
          </g>
        ))}

        {last && !activePt && (
          <text x={Math.min(last.cx + 8, W - pad.r)} y={last.cy - 10} textAnchor={last.cx > W - 80 ? 'end' : 'start'} fontSize="11" fill="#e6edf5" fontFamily="JetBrains Mono Variable, monospace">
            {formatNumber(last.value)}
          </text>
        )}
      </svg>

      {activePt && (
        <div
          className="pointer-events-none absolute -translate-x-1/2 -translate-y-full ms-glass rounded-lg px-2.5 py-1.5 text-xs whitespace-nowrap"
          style={{ left: `${(activePt.cx / W) * 100}%`, top: `${(activePt.cy / H) * 100}%`, marginTop: -10 }}
        >
          <div className="ms-num text-white font-semibold">
            {activePt.raw ?? formatNumber(activePt.value)} <span className="text-ink-mute font-normal">{series.unit}</span>
          </div>
          <div className="text-ink-mute">{activePt.synthetic ? `Baseline, ${activePt.label}` : activePt.label || formatShortDate(activePt.t)}</div>
        </div>
      )}
    </div>
  );
}

/** Tiny inline sparkline used in lists. */
export function Sparkline({ points = [], width = 72, height = 22, className }) {
  if (!points || points.length < 2) return null;
  const vals = points.map((p) => p.value);
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const step = width / (points.length - 1);
  const d = points.map((p, i) => `${i ? 'L' : 'M'}${(i * step).toFixed(1)},${(height - 3 - ((p.value - min) / span) * (height - 6)).toFixed(1)}`).join(' ');
  const rising = vals[vals.length - 1] >= vals[0];
  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} className={className} aria-hidden="true">
      <path d={d} fill="none" stroke={rising ? '#67e8f9' : '#fbbf24'} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
