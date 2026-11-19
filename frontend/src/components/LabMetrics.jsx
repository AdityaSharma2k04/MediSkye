import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Search, X, Calendar, AlertTriangle, MessageSquarePlus, Layers, ListFilter } from 'lucide-react';
import { cn } from '../lib/cn';
import {
  metricName,
  metricRange,
  sortFlaggedFirst,
  filterMetrics,
  summarizeTriage,
  organSystemOf,
  describePlacement,
  deltaPct,
  formatDeltaPct,
  isNotableShift,
  metricKey,
} from '../lib/clinical';
import StatusPill from './clinical/StatusPill';
import RangeBar from './clinical/RangeBar';
import DeltaIndicator from './clinical/DeltaIndicator';

const FILTERS = [
  { value: 'all', label: 'All' },
  { value: 'flagged', label: 'Flagged only' },
  { value: 'drops', label: 'Notable drops' },
];

/**
 * Clinical Lab Metrics.
 *
 * layout:
 *  • 'auto'  — ≥640px viewport: dense table with inline range bars;
 *              <640px: touch-friendly Clinical Biomarker Cards.
 *  • 'list'  — always the compact list (used inside the narrow desktop inspector).
 *  • 'table' — always the table (used inside a wide inspector).
 */
export default function LabMetrics({
  metrics = [],
  onBack, // eslint-disable-line no-unused-vars
  layout = 'auto',
  search: controlledSearch,
  onSearchChange,
  filter: controlledFilter,
  onFilterChange,
  onAskAbout,
  highlightKey,
  showHeader = true,
}) {
  const [localSearch, setLocalSearch] = useState('');
  const [localFilter, setLocalFilter] = useState('all');
  const [grouped, setGrouped] = useState(false);

  const search = controlledSearch !== undefined ? controlledSearch : localSearch;
  const setSearch = onSearchChange || setLocalSearch;
  const filter = controlledFilter !== undefined ? controlledFilter : localFilter;
  const setFilter = onFilterChange || setLocalFilter;

  const collectedAt = metrics?.collected_at;
  const isFuture = metrics?.is_future_collection_date;
  const hasMetrics = Array.isArray(metrics) && metrics.length > 0;

  const triage = useMemo(() => summarizeTriage(hasMetrics ? metrics : []), [metrics, hasMetrics]);

  const hasPriorData = useMemo(() => {
    if (!hasMetrics) return false;
    return metrics.some((m) => m && (m.previous_value != null || m.delta_abs != null || m.delta_pct != null || m.delta_alert != null));
  }, [metrics, hasMetrics]);

  const sortedMetrics = useMemo(() => sortFlaggedFirst(hasMetrics ? metrics : []), [metrics, hasMetrics]);

  const visibleMetrics = useMemo(() => {
    const byFilter = filterMetrics(sortedMetrics, filter);
    if (!search.trim()) return byFilter;
    const q = search.toLowerCase();
    return byFilter.filter((m) => metricName(m).toLowerCase().includes(q) || organSystemOf(m).label.toLowerCase().includes(q));
  }, [sortedMetrics, filter, search]);

  const groups = useMemo(() => {
    if (!grouped) return [{ key: 'all', label: null, rows: visibleMetrics }];
    const map = new Map();
    visibleMetrics.forEach((row) => {
      const sys = organSystemOf(row);
      if (!map.has(sys.key)) map.set(sys.key, { key: sys.key, label: sys.label, rows: [] });
      map.get(sys.key).rows.push(row);
    });
    return [...map.values()];
  }, [grouped, visibleMetrics]);

  const counts = { all: triage.total, flagged: filterMetrics(metrics || [], 'flagged').length, drops: triage.drops };

  const tableContainerRef = useRef(null);
  const [canScrollRight, setCanScrollRight] = useState(false);

  const checkScroll = useCallback(() => {
    const el = tableContainerRef.current;
    if (!el) return;
    setCanScrollRight(el.scrollLeft + el.clientWidth < el.scrollWidth - 2);
  }, []);

  useEffect(() => {
    const el = tableContainerRef.current;
    if (!el) return;
    checkScroll();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(checkScroll);
    ro.observe(el);
    return () => ro.disconnect();
  }, [checkScroll, visibleMetrics]);

  return (
    <div className="animate-fade-in py-1">
      {showHeader && (
        <div className={cn('mb-4 flex flex-col gap-2', layout !== 'list' && 'sm:flex-row sm:items-end sm:justify-between')}>
          <div>
            <h2 className="ms-display text-[22px] leading-tight text-slate-900">Clinical Lab Metrics</h2>
            {hasMetrics && (
              <p className="text-xs mt-1 text-ink-mute">
                {metrics.length} test{metrics.length !== 1 ? 's' : ''} extracted, flagged values first
              </p>
            )}
          </div>

          {collectedAt && (
            <div className="flex items-center gap-1.5 self-start sm:self-auto">
              {isFuture ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-50 text-amber-700 border border-amber-200">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Synthetic / Future-Dated Specimen: {collectedAt}
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg text-xs font-medium bg-slate-100 text-ink-soft border border-slate-200">
                  <Calendar className="w-3.5 h-3.5 text-ink-mute" />
                  Specimen Collected: <span className="ms-num">{collectedAt}</span>
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {hasMetrics && (
        <div className="mb-3 space-y-2.5">
          <div className="relative">
            <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-ink-faint" />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search tests or systems, e.g. Ferritin, Lipids…"
              aria-label="Search lab tests"
              className="w-full h-10 pl-9 pr-9 text-sm rounded-xl bg-graphite text-slate-900 placeholder:text-slate-400 border border-slate-200 focus:outline-none focus:border-cyan-600 focus:ring-4 focus:ring-cyan-500/10 transition"
            />
            {search && (
              <button
                type="button"
                onClick={() => setSearch('')}
                className="absolute right-1.5 top-1/2 -translate-y-1/2 w-8 h-8 rounded-lg flex items-center justify-center text-ink-mute hover:text-slate-900 hover:bg-slate-100"
                aria-label="Clear search"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          <div className={cn('flex items-center gap-2 -mx-1 px-1', layout === 'list' ? 'flex-wrap' : 'overflow-x-auto no-scrollbar')}>
            <ListFilter className="w-3.5 h-3.5 text-ink-faint shrink-0" aria-hidden="true" />
            {FILTERS.map((f) => {
              const active = filter === f.value;
              return (
                <button
                  key={f.value}
                  type="button"
                  aria-pressed={active}
                  onClick={() => setFilter(f.value)}
                  className={cn(
                    'ms-tap shrink-0 inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-xs font-medium border transition',
                    active
                      ? 'bg-cyan-50 border-cyan-200 text-cyan-800'
                      : 'bg-slate-50 border-slate-200 text-slate-600 hover:text-slate-900 hover:border-slate-300'
                  )}
                >
                  {f.label}
                  <span className={cn('ms-num text-xs px-1.5 rounded-full', active ? 'bg-cyan-100 text-cyan-800' : 'bg-slate-200 text-slate-600')}>{counts[f.value]}</span>
                </button>
              );
            })}
            {layout !== 'list' && <span className="w-px h-5 bg-slate-200 shrink-0 mx-0.5" aria-hidden="true" />}
            <button
              type="button"
              aria-pressed={grouped}
              onClick={() => setGrouped((g) => !g)}
              className={cn(
                'ms-tap shrink-0 inline-flex items-center gap-1.5 h-8 px-3 rounded-full text-xs font-medium border transition',
                grouped ? 'bg-slate-200 border-slate-300 text-slate-900' : 'bg-slate-50 border-slate-200 text-slate-600 hover:text-slate-900'
              )}
            >
              <Layers className="w-3.5 h-3.5" />
              By organ system
            </button>
          </div>
        </div>
      )}

      {!hasMetrics ? (
        <EmptyBlock title="No lab metrics available for this report." body="Metrics appear here once values are extracted from a text-based report." />
      ) : visibleMetrics.length === 0 ? (
        <EmptyBlock
          title={search ? 'No tests match your search.' : 'Nothing matches this filter.'}
          body={search ? 'Try a different test name, or clear the search to see all values.' : 'Switch to All to see every extracted value.'}
        />
      ) : (
        <>
          {(layout === 'auto' || layout === 'table') && (
            <div className={cn(layout === 'auto' ? 'hidden sm:block' : 'block', 'relative rounded-2xl ms-surface overflow-hidden')}>
              <div ref={tableContainerRef} onScroll={checkScroll} className="w-full overflow-x-auto">
                <table className="min-w-[680px] w-full text-left text-[13px] border-collapse">
                  <thead className="bg-graphite">
                    <tr className="border-b border-slate-200">
                      <Th>Test Name</Th>
                      <Th>Value</Th>
                      <Th>Unit</Th>
                      <Th className="min-w-[180px]">Reference Range</Th>
                      {hasPriorData && (
                        <>
                          <Th>Previous (Date)</Th>
                          <Th>Change (Δ %)</Th>
                        </>
                      )}
                      <Th>Status</Th>
                    </tr>
                  </thead>
                  {groups.map((g) => (
                    <tbody key={g.key} className="divide-y divide-slate-100">
                      {g.label && (
                        <tr className="bg-slate-50">
                          <td colSpan={hasPriorData ? 7 : 5} className="px-3.5 pt-3 pb-1.5 text-xs font-semibold text-ink-mute">
                            {g.label} <span className="ms-num text-ink-faint">({g.rows.length})</span>
                          </td>
                        </tr>
                      )}
                      {g.rows.map((row, idx) => (
                        <MetricRow
                          key={`${metricKey(row)}-${idx}`}
                          row={row}
                          hasPriorData={hasPriorData}
                          highlighted={highlightKey && metricKey(row) === highlightKey}
                          onAskAbout={onAskAbout}
                        />
                      ))}
                    </tbody>
                  ))}
                </table>
              </div>
              {canScrollRight && (
                <div
                  aria-hidden="true"
                  className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-white to-transparent"
                />
              )}
            </div>
          )}

          {(layout === 'auto' || layout === 'list') && (
            <div className={cn(layout === 'auto' ? 'block sm:hidden' : 'block', 'space-y-4')}>
              {groups.map((g) => (
                <section key={g.key} aria-label={g.label || 'Biomarkers'}>
                  {g.label && (
                    <h3 className="px-1 mb-2 text-xs font-semibold text-ink-mute">
                      {g.label} <span className="ms-num text-ink-faint">({g.rows.length})</span>
                    </h3>
                  )}
                  <div className="space-y-2">
                    {g.rows.map((row, idx) => (
                      <BiomarkerCard
                        key={`${metricKey(row)}-${idx}`}
                        row={row}
                        highlighted={highlightKey && metricKey(row) === highlightKey}
                        onAskAbout={onAskAbout}
                      />
                    ))}
                  </div>
                </section>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

function Th({ children, className }) {
  return <th className={cn('px-3.5 py-2.5 text-xs font-semibold text-ink-mute whitespace-nowrap', className)}>{children}</th>;
}

function MetricRow({ row, hasPriorData, highlighted, onAskAbout }) {
  const testName = metricName(row);
  const d = deltaPct(row);
  return (
    <tr data-testid="metric-row" className={cn('group transition-colors hover:bg-slate-50', highlighted && 'bg-cyan-50/50')}>
      <td className="px-3.5 py-3 font-medium text-slate-900">
        <div className="flex items-center gap-2">
          <span>{testName}</span>
          {onAskAbout && (
            <button
              type="button"
              onClick={() => onAskAbout(row)}
              aria-label={`Ask MediSkye about ${testName}`}
              title={`Ask MediSkye about ${testName}`}
              className="opacity-0 group-hover:opacity-100 focus:opacity-100 w-7 h-7 rounded-lg flex items-center justify-center text-slate-400 hover:text-cyan-700 hover:bg-cyan-50 transition"
            >
              <MessageSquarePlus className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      </td>
      <td className="px-3.5 py-3 font-semibold text-slate-900 whitespace-nowrap ms-num">{row.value ?? '—'}</td>
      <td className="px-3.5 py-3 text-ink-mute whitespace-nowrap ms-num text-xs">{row.unit || '—'}</td>
      <td className="px-3.5 py-3 text-ink-mute">
        <div className="ms-num text-xs whitespace-nowrap">{metricRange(row) || '—'}</div>
        <RangeBar row={row} size="sm" className="mt-1.5 max-w-[200px]" />
      </td>
      {hasPriorData && (
        <>
          <td className="px-3.5 py-3 text-ink-mute whitespace-nowrap">
            {row.previous_value ? (
              <div>
                <span className="font-medium text-ink-soft ms-num">{row.previous_value}</span>
                {row.previous_date && <span className="text-xs text-ink-faint block">{row.previous_date}</span>}
              </div>
            ) : (
              '—'
            )}
          </td>
          <td className="px-3.5 py-3 whitespace-nowrap">
            {d !== null ? (
              <span className={cn('ms-num text-xs font-medium', row.delta_alert || isNotableShift(row) ? 'text-amber-700 font-semibold' : 'text-ink-mute')}>
                {row.delta_abs ? `${row.delta_abs} ` : ''}({formatDeltaPct(d)})
              </span>
            ) : (
              <span className="text-ink-faint">—</span>
            )}
          </td>
        </>
      )}
      <td className="px-3.5 py-3 whitespace-nowrap">
        <StatusPill row={row} />
      </td>
    </tr>
  );
}

/** Touch-first Clinical Biomarker Card. */
function BiomarkerCard({ row, highlighted, onAskAbout }) {
  const testName = metricName(row);
  const placement = describePlacement(row);
  const hasPrev = row?.previous_value !== null && row?.previous_value !== undefined && row?.previous_value !== '';
  return (
    <article
      data-testid="biomarker-card"
      className={cn(
        'p-3.5 rounded-2xl ms-surface transition-colors',
        highlighted && 'border-cyan-200 bg-cyan-50/50'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="text-[14px] font-semibold text-slate-900 leading-snug">{testName}</div>
          <div className="text-xs text-ink-faint mt-0.5">{organSystemOf(row).label}</div>
        </div>
        <StatusPill row={row} size="sm" className="shrink-0" />
      </div>

      <div className="mt-3 flex items-baseline gap-1.5">
        <span className="ms-num text-[22px] leading-none font-semibold text-slate-900">{row.value ?? '—'}</span>
        {row.unit && <span className="ms-num text-xs text-ink-mute">{row.unit}</span>}
      </div>

      <RangeBar row={row} showScale className="mt-2.5" />

      <div className="mt-1 flex items-center justify-between gap-2 text-xs">
        <span className="text-ink-mute truncate">
          {placement || (
            <>
              Ref <span className="ms-num">{metricRange(row) || '—'}</span>
            </>
          )}
        </span>
        {!hasPrev && <span className="text-ink-faint shrink-0">No prior baseline</span>}
      </div>

      {(hasPrev || onAskAbout) && (
        <div className="mt-2.5 pt-2.5 border-t border-slate-200 flex items-center justify-between gap-2">
          {hasPrev ? (
            <div className="min-w-0">
              <DeltaIndicator row={row} compact />
              {row.previous_date && <div className="text-xs text-ink-faint mt-0.5">since {row.previous_date}</div>}
            </div>
          ) : (
            <span />
          )}
          {onAskAbout && (
            <button
              type="button"
              onClick={() => onAskAbout(row)}
              aria-label={`Ask MediSkye about ${testName}`}
              className="ms-tap shrink-0 inline-flex items-center gap-1.5 h-9 px-3 rounded-xl text-xs font-medium text-cyan-800 bg-cyan-50 border border-cyan-200 hover:bg-cyan-100 transition"
            >
              <MessageSquarePlus className="w-3.5 h-3.5" />
              Ask
            </button>
          )}
        </div>
      )}
    </article>
  );
}

function EmptyBlock({ title, body }) {
  return (
    <div className="py-10 px-6 text-center rounded-2xl border border-dashed border-slate-200 animate-fade-in">
      <div className="w-11 h-11 rounded-2xl flex items-center justify-center mx-auto mb-3 bg-slate-100 text-ink-mute">
        <Search className="w-5 h-5" />
      </div>
      <div className="text-sm font-semibold mb-1 text-slate-900">{title}</div>
      <div className="text-xs max-w-xs mx-auto text-ink-mute">{body}</div>
    </div>
  );
}
