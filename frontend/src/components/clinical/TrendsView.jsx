import React, { useEffect, useMemo, useState } from 'react';
import { LineChart, Loader2, Upload, Info } from 'lucide-react';
import { cn } from '../../lib/cn';
import { rankTrendSeries, formatDeltaPct, formatNumber } from '../../lib/clinical';
import TrendChart, { Sparkline } from './TrendChart';

/**
 * Longitudinal biomarker explorer.
 * Picks the most clinically relevant series first (flagged → multi-point → largest change).
 */
export default function TrendsView({ series, loading, source, reportCount = 0, latestMetrics = [], focusKey, onUpload }) {
  const ranked = useMemo(() => rankTrendSeries(series || new Map(), latestMetrics), [series, latestMetrics]);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (focusKey && ranked.some((s) => s.key === focusKey)) setSelected(focusKey);
  }, [focusKey, ranked]);

  const current = ranked.find((s) => s.key === selected) || ranked.find((s) => s.points.length > 1) || ranked[0];
  const multiPoint = ranked.filter((s) => s.points.length > 1);

  if (loading && !ranked.length) {
    return (
      <div className="py-12 flex flex-col items-center text-center gap-3" role="status">
        <Loader2 className="w-5 h-5 animate-spin text-cyan-600" />
        <div className="text-sm text-ink-soft">Lining up readings across your reports…</div>
      </div>
    );
  }

  if (!ranked.length || !multiPoint.length) {
    return (
      <div className="py-10 px-6 text-center rounded-2xl border border-dashed border-slate-200">
        <div className="w-11 h-11 rounded-2xl mx-auto mb-3 flex items-center justify-center bg-slate-100 text-ink-mute">
          <LineChart className="w-5 h-5" />
        </div>
        <div className="text-sm font-semibold text-slate-900 mb-1">Trends need two readings</div>
        <p className="text-xs text-ink-mute max-w-xs mx-auto mb-4">
          Upload an earlier or later report for this patient and MediSkye will chart how each biomarker moved between them.
        </p>
        {onUpload && (
          <button
            type="button"
            onClick={onUpload}
            className="ms-tap inline-flex items-center gap-2 h-10 px-4 rounded-xl text-xs font-semibold bg-cyan-600 text-white hover:bg-cyan-700 transition"
          >
            <Upload className="w-3.5 h-3.5" /> Add another report
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {current && (
        <section className="rounded-2xl ms-surface p-4">
          <div className="flex items-start justify-between gap-3 mb-2">
            <div className="min-w-0">
              <h3 className="text-[15px] font-semibold text-slate-900 truncate">{current.name}</h3>
              <div className="text-xs text-ink-mute mt-0.5">
                Reference <span className="ms-num">{current.range || 'not stated'}</span>
                {current.unit ? <span className="ms-num"> {current.unit}</span> : null}
              </div>
            </div>
            {current.change !== null && (
              <div className="text-right shrink-0">
                <div className={cn('ms-num text-lg font-semibold leading-none', Math.abs(current.change) >= 10 ? 'text-amber-700' : 'text-slate-900')}>
                  {current.change < 0 ? '↓' : '↑'} {formatDeltaPct(Math.abs(current.change)).replace('+', '')}
                </div>
                <div className="text-xs text-ink-faint mt-1">first → latest</div>
              </div>
            )}
          </div>
          <TrendChart series={current} />
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-faint">
            <span className="inline-flex items-center gap-1.5"><span className="w-3 h-2 rounded-sm bg-emerald-500/25 border border-emerald-500/50" /> Reference interval</span>
            <span className="inline-flex items-center gap-1.5"><span className="w-2 h-2 rounded-full border border-dashed border-slate-400" /> Baseline from report</span>
          </div>
        </section>
      )}

      <section aria-label="Biomarkers with history">
        <h4 className="px-1 mb-2 text-xs font-semibold text-ink-mute">
          {multiPoint.length} biomarker{multiPoint.length === 1 ? '' : 's'} with history
        </h4>
        <ul className="space-y-1">
          {multiPoint.map((s) => {
            const isActive = current?.key === s.key;
            const last = s.points[s.points.length - 1];
            const notable = s.change !== null && Math.abs(s.change) >= 10;
            return (
              <li key={s.key}>
                <button
                  type="button"
                  onClick={() => setSelected(s.key)}
                  aria-pressed={isActive}
                  className={cn(
                    'w-full flex items-center gap-3 px-3 py-2 rounded-xl text-left border transition',
                    isActive ? 'bg-cyan-50 border-cyan-200 text-cyan-900' : 'border-transparent hover:bg-slate-100'
                  )}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-xs font-medium text-ink truncate">{s.name}</span>
                    <span className="block text-xs text-ink-faint ms-num">
                      {s.points.length} readings, latest {formatNumber(last.value)} {s.unit}
                    </span>
                  </span>
                  <Sparkline points={s.points} />
                  <span className={cn('ms-num text-xs font-semibold w-14 text-right', notable ? 'text-amber-700' : 'text-ink-mute')}>
                    {s.change === null ? '—' : formatDeltaPct(s.change)}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </section>

      <p className="flex items-start gap-2 text-xs text-ink-faint px-1">
        <Info className="w-3.5 h-3.5 mt-px shrink-0" />
        {source === 'server'
          ? 'Series served by the MediSkye trends service.'
          : reportCount > 1
            ? `Computed on this device from ${reportCount} reports.`
            : 'Built from the baseline and follow-up values printed in this report.'}
      </p>
    </div>
  );
}

