import React, { useMemo } from 'react';
import { ChevronRight, ShieldCheck, TriangleAlert, TrendingDown } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import { summarizeTriage, metricName, statusTone, TONE, metricKey } from '../../lib/clinical';
import RangeBar from './RangeBar';
import StatusPill from './StatusPill';

/**
 * Triage summary + organ-system grouping.
 * Answers the first question a clinician asks: "what needs attention, and where?"
 */
export default function OrganSystemsOverview({ metrics = [], onSelectMetric, onApplyFilter, compact = false }) {
  const { t } = useTranslation();
  const triage = useMemo(() => summarizeTriage(metrics), [metrics]);
  if (!triage.total) return null;

  const segments = [
    { key: 'rose', n: triage.critical + triage.high, label: 'High or critical' },
    { key: 'amber', n: triage.low + triage.borderline, label: 'Low or borderline' },
    { key: 'emerald', n: triage.normal, label: 'In range' },
    { key: 'neutral', n: triage.unknown, label: 'Unclassified' },
  ].filter((s) => s.n > 0);

  const headline =
    triage.flagged === 0
      ? t('workbench.all_in_range', { total: triage.total, defaultValue: `All ${triage.total} values are within their reference intervals` })
      : t('workbench.values_need_attention', { flagged: triage.flagged, total: triage.total, defaultValue: `${triage.flagged} of ${triage.total} values need attention` });

  return (
    <div className="space-y-4">
      <section className="rounded-2xl ms-surface p-4">
        <div className="flex items-start gap-3">
          <div
            className={cn(
              'w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border',
              triage.flagged ? 'bg-amber-500/10 border-amber-500/25 text-amber-300' : 'bg-emerald-500/10 border-emerald-500/25 text-emerald-300'
            )}
          >
            {triage.flagged ? <TriangleAlert className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
          </div>
          <div className="min-w-0">
            <h3 className="ms-display text-[17px] text-white leading-snug">{headline}</h3>
            <p className="text-xs text-ink-mute mt-1">
              {triage.shifts > 0
                ? `${triage.shifts} moved by 10% or more since the previous report.`
                : 'No large shifts against the previous report.'}
            </p>
          </div>
        </div>

        <div className="mt-4 flex h-2.5 w-full overflow-hidden rounded-full bg-white/[0.05]" role="img" aria-label={segments.map((s) => `${s.n} ${s.label}`).join(', ')}>
          {segments.map((s) => (
            <div key={s.key} style={{ width: `${(s.n / triage.total) * 100}%`, background: TONE[s.key].hex }} className="h-full first:rounded-l-full last:rounded-r-full opacity-90" />
          ))}
        </div>
        <ul className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-ink-mute">
          {segments.map((s) => (
            <li key={s.key} className="inline-flex items-center gap-1.5">
              <span className={cn('w-2 h-2 rounded-full', TONE[s.key].dot)} />
              <span className="ms-num text-ink-soft">{s.n}</span> {s.label}
            </li>
          ))}
        </ul>

        {onApplyFilter && (
          <div className="mt-4 grid grid-cols-3 gap-2">
            <QuickFilter label="All values" n={triage.total} onClick={() => onApplyFilter('all')} />
            <QuickFilter label="Flagged only" n={triage.flagged} tone="amber" onClick={() => onApplyFilter('flagged')} />
            <QuickFilter label="Notable drops" n={triage.drops} tone="amber" icon={TrendingDown} onClick={() => onApplyFilter('drops')} />
          </div>
        )}
      </section>

      <div className={cn('grid gap-3', compact ? 'grid-cols-1' : 'grid-cols-1 xl:grid-cols-2')}>
        {triage.systems.map((sys) => (
          <SystemCard key={sys.key} system={sys} onSelectMetric={onSelectMetric} />
        ))}
      </div>
    </div>
  );
}

function QuickFilter({ label, n, onClick, tone, icon: Icon }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="ms-tap text-left rounded-xl px-3 py-2 bg-white/[0.025] border border-white/[0.07] hover:border-white/[0.16] hover:bg-white/[0.05] transition"
    >
      <div className={cn('ms-num text-lg font-semibold leading-none', tone === 'amber' && n > 0 ? 'text-amber-300' : 'text-white')}>{n}</div>
      <div className="mt-1 text-[11px] text-ink-mute flex items-center gap-1">
        {Icon && <Icon className="w-3 h-3" />}
        {label}
      </div>
    </button>
  );
}

function SystemCard({ system, onSelectMetric }) {
  const shown = system.metrics.slice(0, 4);
  const rest = system.metrics.length - shown.length;
  const worstTone = system.flagged ? (system.worst <= 1 ? 'rose' : 'amber') : 'emerald';
  return (
    <section className="rounded-2xl ms-surface p-3.5" aria-label={system.label} data-testid="organ-system-card">
      <header className="flex items-center justify-between gap-2 mb-2.5">
        <div className="flex items-center gap-2 min-w-0">
          <span className={cn('w-1.5 h-4 rounded-full', TONE[worstTone].dot)} aria-hidden="true" />
          <h4 className="text-[13px] font-semibold text-white truncate">{system.label}</h4>
        </div>
        <span className={cn('text-[11px] ms-num px-2 py-0.5 rounded-full border', system.flagged ? `${TONE[worstTone].bg} ${TONE[worstTone].text} ${TONE[worstTone].border}` : 'bg-white/[0.04] text-ink-mute border-white/[0.08]')}>
          {system.flagged ? `${system.flagged} flagged` : `${system.metrics.length} in range`}
        </span>
      </header>
      <ul className="space-y-1">
        {shown.map((row, i) => (
          <li key={`${metricKey(row)}-${i}`}>
            <button
              type="button"
              onClick={() => onSelectMetric?.(row)}
              className="w-full grid grid-cols-[minmax(0,1fr)_auto] items-center gap-x-3 gap-y-1 rounded-xl px-2 py-1.5 -mx-1 text-left hover:bg-white/[0.04] transition"
            >
              <span className="text-xs text-ink-soft truncate">{metricName(row)}</span>
              <span className={cn('ms-num text-xs font-semibold text-right', TONE[statusTone(row)].text)}>
                {row.value} <span className="text-ink-faint font-normal">{row.unit}</span>
              </span>
              <RangeBar row={row} size="sm" className="col-span-2" />
            </button>
          </li>
        ))}
      </ul>
      {rest > 0 && (
        <button
          type="button"
          onClick={() => onSelectMetric?.(system.metrics[shown.length], system)}
          className="mt-1.5 inline-flex items-center gap-1 text-[11px] text-ink-mute hover:text-white"
        >
          {rest} more in {system.label} <ChevronRight className="w-3 h-3" />
        </button>
      )}
      {system.metrics.length === 1 && system.flagged === 0 && (
        <div className="mt-1">
          <StatusPill row={system.metrics[0]} size="sm" />
        </div>
      )}
    </section>
  );
}
