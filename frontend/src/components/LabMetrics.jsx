import React, { useState, useMemo } from 'react';
import { Search, X, Calendar, AlertTriangle } from 'lucide-react';

// ── Accessible Status Pill with Directional Icons ────────────────────────────
function renderStatusPill(row) {
  const status = String(row?.status || 'Normal').trim();
  const s = status.toLowerCase();
  const deltaAlert = row?.delta_alert;

  if (s === 'high' || s === 'critical') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-rose-500/10 text-rose-600 dark:text-rose-400 border border-rose-500/20 whitespace-nowrap">
        <span>↑</span> {status}
      </span>
    );
  }

  if (s === 'low') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 whitespace-nowrap">
        <span>↓</span> {status}
      </span>
    );
  }

  if (deltaAlert) {
    const isDrop = deltaAlert.toLowerCase().includes('drop');
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20 whitespace-nowrap">
        <span>{isDrop ? '↘' : '↗'}</span> {deltaAlert}
      </span>
    );
  }

  if (s === 'normal') {
    return (
      <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border border-emerald-500/20 whitespace-nowrap">
        <span>✓</span> Normal
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-semibold bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border border-zinc-500/20 whitespace-nowrap">
      {status}
    </span>
  );
}

// ── Main LabMetrics Component ─────────────────────────────────────────────────
export default function LabMetrics({ metrics = [], darkMode, onBack }) {
  const [search, setSearch] = useState('');

  const textPrimary   = darkMode ? 'text-white'    : 'text-zinc-900';
  const textSecondary = darkMode ? 'text-zinc-400' : 'text-zinc-500';
  const borderCol     = darkMode ? 'border-zinc-800' : 'border-zinc-200';
  const cardBg        = darkMode ? 'bg-[#121212]'  : 'bg-white';
  const theadBg       = darkMode ? 'bg-zinc-900/80' : 'bg-zinc-50';
  const hoverRowBg    = darkMode ? 'hover:bg-zinc-900/50' : 'hover:bg-zinc-50/80';

  const collectedAt = metrics?.collected_at;
  const isFuture = metrics?.is_future_collection_date;

  const hasPriorData = useMemo(() => {
    if (!metrics || !Array.isArray(metrics)) return false;
    return metrics.some(
      (m) => m && (m.previous_value != null || m.delta_abs != null || m.delta_pct != null || m.delta_alert != null)
    );
  }, [metrics]);

  // Deterministic sorting: Flagged (High / Low / Critical / delta_alert) first, then Normal
  const sortedMetrics = useMemo(() => {
    if (!metrics || !Array.isArray(metrics)) return [];
    const getPriority = (m) => {
      const s = String(m?.status || '').trim().toLowerCase();
      if (s === 'high' || s === 'low' || s === 'critical' || s === 'abnormal' || m?.delta_alert) {
        return 0;
      }
      return 1;
    };
    return [...metrics].sort((a, b) => getPriority(a) - getPriority(b));
  }, [metrics]);

  // Search filter
  const filteredMetrics = useMemo(() => {
    if (!search.trim()) return sortedMetrics;
    const q = search.toLowerCase();
    return sortedMetrics.filter((m) => (m.test || m.name || '').toLowerCase().includes(q));
  }, [sortedMetrics, search]);

  const hasMetrics = metrics && Array.isArray(metrics) && metrics.length > 0;

  return (
    <div className="animate-fade-in py-4">
      {/* Header row */}
      <div className="mb-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h2 className={`text-xl font-bold tracking-tight ${textPrimary}`}>Clinical Lab Metrics</h2>
          {hasMetrics && (
            <p className={`text-xs mt-0.5 ${textSecondary}`}>
              {metrics.length} test{metrics.length !== 1 ? 's' : ''} extracted • abnormal values shown first
            </p>
          )}
        </div>

        {/* Specimen Date Badge */}
        {collectedAt && (
          <div className="flex items-center gap-1.5 self-start sm:self-auto">
            {isFuture ? (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-amber-500/10 text-amber-600 dark:text-amber-400 border border-amber-500/20">
                <AlertTriangle className="w-3.5 h-3.5" />
                Synthetic / Future-Dated Specimen: {collectedAt}
              </span>
            ) : (
              <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-xs font-medium bg-zinc-500/10 text-zinc-600 dark:text-zinc-400 border border-zinc-500/20">
                <Calendar className="w-3.5 h-3.5" />
                Specimen Collected: {collectedAt}
              </span>
            )}
          </div>
        )}
      </div>

      {/* Search Input (only shown when there are metrics) */}
      {hasMetrics && (
        <div className="relative mb-3">
          <Search className={`w-3.5 h-3.5 absolute left-3 top-2.5 ${textSecondary}`} />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search tests…"
            aria-label="Search lab tests"
            className={`w-full pl-8 pr-8 py-2 text-xs rounded-xl border focus:outline-none transition-all ${
              darkMode
                ? 'bg-zinc-900 text-white placeholder-zinc-500 border-zinc-800 focus:border-zinc-700'
                : 'bg-white text-zinc-900 placeholder-zinc-400 border-zinc-200 focus:border-zinc-400'
            }`}
          />
          {search && (
            <button
              onClick={() => setSearch('')}
              className={`absolute right-2.5 top-2 ${textSecondary}`}
              aria-label="Clear search"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          )}
        </div>
      )}

      {/* Main Clinical Data Table / Mobile Cards / Empty State */}
      {!hasMetrics ? (
        <div className={`py-10 text-center rounded-xl border border-dashed animate-fade-in ${borderCol}`}>
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-3 ${
            darkMode ? 'bg-zinc-800/80 text-zinc-400' : 'bg-zinc-100 text-zinc-500'
          }`}>
            <Search className="w-5 h-5" />
          </div>
          <div className={`text-sm font-semibold mb-1 ${textPrimary}`}>
            No lab metrics available for this report.
          </div>
          <div className={`text-xs max-w-xs mx-auto ${textSecondary}`}>
            Metrics appear here once values are extracted from a text-based report.
          </div>
        </div>
      ) : filteredMetrics.length === 0 ? (
        <div className={`py-10 text-center rounded-xl border border-dashed animate-fade-in ${borderCol}`}>
          <div className={`w-12 h-12 rounded-2xl flex items-center justify-center mx-auto mb-3 ${
            darkMode ? 'bg-zinc-800/80 text-zinc-400' : 'bg-zinc-100 text-zinc-500'
          }`}>
            <Search className="w-5 h-5" />
          </div>
          <div className={`text-sm font-semibold mb-1 ${textPrimary}`}>
            No tests match your search.
          </div>
          <div className={`text-xs ${textSecondary}`}>
            Try a different test name, or clear the search to see all values.
          </div>
        </div>
      ) : (
        <>
          {/* 1. Desktop & Tablet Table (>= 640px) */}
          <div className={`hidden sm:block rounded-xl border overflow-hidden ${cardBg} ${borderCol}`}>
            <div className="w-full overflow-x-auto pb-4">
              <table
                className="min-w-full min-w-[600px] text-left text-xs"
                style={{ width: '100%', borderCollapse: 'collapse' }}
              >
                <thead className={theadBg}>
                  <tr className={`border-b ${borderCol}`}>
                    <th style={{ padding: '10px 12px' }} className={`font-semibold ${textSecondary} whitespace-nowrap`}>Test Name</th>
                    <th style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }} className={`font-semibold ${textSecondary} whitespace-nowrap`}>Value</th>
                    <th style={{ padding: '10px 12px' }} className={`font-semibold ${textSecondary} whitespace-nowrap`}>Unit</th>
                    <th style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }} className={`font-semibold ${textSecondary} whitespace-nowrap`}>Reference Range</th>
                    {hasPriorData && (
                      <>
                        <th style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }} className={`font-semibold ${textSecondary} whitespace-nowrap`}>Previous (Date)</th>
                        <th style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }} className={`font-semibold ${textSecondary} whitespace-nowrap`}>Change (Δ %)</th>
                      </>
                    )}
                    <th style={{ padding: '10px 12px' }} className={`font-semibold ${textSecondary} whitespace-nowrap`}>Status</th>
                  </tr>
                </thead>
                <tbody className={`divide-y ${borderCol}`}>
                  {filteredMetrics.map((row, idx) => {
                    const testName = row.test || row.name || '—';
                    const prevVal = row.previous_value;
                    const prevDate = row.previous_date;
                    const deltaPct = row.delta_pct;
                    const deltaAbs = row.delta_abs;

                    return (
                      <tr
                        key={idx}
                        className={`transition-colors ${hoverRowBg}`}
                        style={{ borderBottom: `1px solid ${darkMode ? '#27272a' : '#f4f4f5'}` }}
                      >
                        <td style={{ padding: '10px 12px' }} className={`font-medium ${textPrimary}`}>
                          {testName}
                        </td>
                        <td
                          style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}
                          className={`font-semibold ${textPrimary} whitespace-nowrap`}
                        >
                          {row.value ?? '—'}
                        </td>
                        <td style={{ padding: '10px 12px' }} className={`${textSecondary} whitespace-nowrap`}>
                          {row.unit || '—'}
                        </td>
                        <td
                          style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}
                          className={`${textSecondary} whitespace-nowrap`}
                        >
                          {row.range || row.reference_range || '—'}
                        </td>
                        {hasPriorData && (
                          <>
                            <td
                              style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}
                              className={`${textSecondary} whitespace-nowrap`}
                            >
                              {prevVal ? (
                                <div>
                                  <span className={`font-medium ${textPrimary}`}>{prevVal}</span>
                                  {prevDate && <span className="text-[11px] text-zinc-400 block">{prevDate}</span>}
                                </div>
                              ) : (
                                '—'
                              )}
                            </td>
                            <td
                              style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}
                              className="whitespace-nowrap"
                            >
                              {deltaPct !== null && deltaPct !== undefined ? (
                                <span
                                  className={`font-medium ${
                                    row.delta_alert
                                      ? 'text-amber-500 font-semibold'
                                      : deltaPct < 0
                                      ? 'text-zinc-600 dark:text-zinc-400'
                                      : 'text-zinc-600 dark:text-zinc-400'
                                  }`}
                                >
                                  {deltaAbs ? `${deltaAbs} ` : ''}
                                  ({deltaPct > 0 ? '+' : ''}{deltaPct}%)
                                </span>
                              ) : (
                                <span className={textSecondary}>—</span>
                              )}
                            </td>
                          </>
                        )}
                        <td style={{ padding: '10px 12px' }} className="whitespace-nowrap">
                          {renderStatusPill(row)}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* 2. Mobile Stacked Clinical Cards (< 640px, optimized for 390px) */}
          <div className="block sm:hidden space-y-2.5">
            {filteredMetrics.map((row, idx) => {
              const testName = row.test || row.name || '—';
              const prevVal = row.previous_value;
              const prevDate = row.previous_date;
              const deltaPct = row.delta_pct;
              const deltaAbs = row.delta_abs;

              return (
                <div
                  key={idx}
                  className={`p-3.5 rounded-xl border ${cardBg} ${borderCol} space-y-2`}
                >
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <div className={`text-sm font-semibold truncate ${textPrimary}`}>{testName}</div>
                      <div className={`text-xs ${textSecondary}`}>
                        Ref: {row.range || row.reference_range || '—'} {row.unit ? `(${row.unit})` : ''}
                      </div>
                    </div>
                    <div className="shrink-0">{renderStatusPill(row)}</div>
                  </div>

                  <div className="flex items-baseline justify-between pt-1.5 border-t border-zinc-100 dark:border-zinc-800/80">
                    <div className="flex items-baseline gap-1">
                      <span className={`text-base font-bold tabular-nums ${textPrimary}`}>{row.value ?? '—'}</span>
                      <span className={`text-xs ${textSecondary}`}>{row.unit || ''}</span>
                    </div>

                    {prevVal ? (
                      <div className="text-right">
                        <span
                          className={`text-xs tabular-nums font-medium ${
                            row.delta_alert
                              ? 'text-amber-500 font-semibold'
                              : 'text-zinc-500 dark:text-zinc-400'
                          }`}
                        >
                          {deltaPct !== null && deltaPct !== undefined
                            ? `${deltaAbs ? deltaAbs + ' ' : ''}(${deltaPct > 0 ? '+' : ''}${deltaPct}%)`
                            : ''}
                          {' '}prev: {prevVal}
                        </span>
                        {prevDate && (
                          <div className="text-[10px] text-zinc-400 dark:text-zinc-500">{prevDate}</div>
                        )}
                      </div>
                    ) : (
                      <span className={`text-xs ${textSecondary}`}>No prior baseline</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
