import React, { useState, useMemo } from 'react';
import { Search, X } from 'lucide-react';

// ── Status plain-text styling (no background pills/badges) ───────────────────
function getStatusColor(status, darkMode) {
  const s = String(status || '').trim().toLowerCase();
  if (s === 'high' || s === 'critical') {
    return darkMode ? '#ef4444' : '#dc2626';
  }
  if (s === 'low') {
    return darkMode ? '#60a5fa' : '#2563eb';
  }
  if (s === 'normal') {
    return darkMode ? '#22c55e' : '#16a34a';
  }
  return darkMode ? '#a1a1aa' : '#6b7280';
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

  // Deterministic sorting: Abnormal (High / Low / Critical / Abnormal) first, then Normal
  const sortedMetrics = useMemo(() => {
    if (!metrics || !Array.isArray(metrics)) return [];
    const getPriority = (status) => {
      const s = String(status || '').trim().toLowerCase();
      if (s === 'high' || s === 'low' || s === 'critical' || s === 'abnormal') {
        return 0;
      }
      return 1;
    };
    return [...metrics].sort((a, b) => getPriority(a.status) - getPriority(b.status));
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
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h2 className={`text-xl font-bold tracking-tight ${textPrimary}`}>Clinical Lab Metrics</h2>
          {hasMetrics && (
            <p className={`text-xs mt-0.5 ${textSecondary}`}>
              {metrics.length} test{metrics.length !== 1 ? 's' : ''} extracted • abnormal values shown first
            </p>
          )}
        </div>
        {onBack && (
          <div className="flex items-center gap-2">
            <button
              onClick={onBack}
              className={`text-xs underline ${darkMode ? 'text-zinc-400 hover:text-white' : 'text-zinc-500 hover:text-zinc-900'}`}
            >
              Back to Chat →
            </button>
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

      {/* Main Clinical Data Table or Empty State */}
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
        <div className={`rounded-xl border overflow-hidden ${cardBg} ${borderCol}`}>
          <table
            className="w-full text-left text-xs"
            style={{ width: '100%', borderCollapse: 'collapse' }}
          >
            <thead className={theadBg}>
              <tr className={`border-b ${borderCol}`}>
                <th style={{ padding: '10px 12px' }} className={`font-semibold ${textSecondary}`}>Test Name</th>
                <th style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }} className={`font-semibold ${textSecondary}`}>Value</th>
                <th style={{ padding: '10px 12px' }} className={`font-semibold ${textSecondary}`}>Unit</th>
                <th style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }} className={`font-semibold ${textSecondary}`}>Reference Range</th>
                <th style={{ padding: '10px 12px' }} className={`font-semibold ${textSecondary}`}>Status</th>
              </tr>
            </thead>
            <tbody className={`divide-y ${borderCol}`}>
              {filteredMetrics.map((row, idx) => {
                const testName = row.test || row.name || '—';
                const status = row.status || 'Normal';
                const statusColor = getStatusColor(status, darkMode);

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
                      className={`font-semibold ${textPrimary}`}
                    >
                      {row.value ?? '—'}
                    </td>
                    <td style={{ padding: '10px 12px' }} className={textSecondary}>
                      {row.unit || '—'}
                    </td>
                    <td
                      style={{ padding: '10px 12px', fontVariantNumeric: 'tabular-nums' }}
                      className={textSecondary}
                    >
                      {row.range || row.reference_range || '—'}
                    </td>
                    <td style={{ padding: '10px 12px' }}>
                      <span
                        style={{
                          fontWeight: 600,
                          color: statusColor,
                          background: 'none',
                          border: 'none',
                          padding: 0,
                        }}
                      >
                        {status}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
