import React, { useState, useMemo } from 'react';
import { ChevronDown, ChevronUp, Download, Search, X } from 'lucide-react';

// ── Category mapping ──────────────────────────────────────────────────────────
const CATEGORY_KEYWORDS = {
  Diabetes:  ['glucose', 'hba1c', 'insulin', 'glycated', 'fasting blood sugar', 'fbs', 'ppbs'],
  Lipid:     ['cholesterol', 'ldl', 'hdl', 'triglyceride', 'vldl', 'non-hdl'],
  Kidney:    ['creatinine', 'urea', 'bun', 'egfr', 'uric acid', 'cystatin', 'albumin/creatinine'],
  Liver:     ['alt', 'ast', 'alp', 'ggt', 'bilirubin', 'albumin', 'total protein', 'sgpt', 'sgot'],
  Blood:     ['hemoglobin', 'hematocrit', 'rbc', 'wbc', 'platelet', 'mcv', 'mch', 'mchc', 'neutrophil', 'lymphocyte', 'eosinophil', 'basophil', 'monocyte', 'cbc'],
  Thyroid:   ['tsh', 't3', 't4', 'free t3', 'free t4', 'thyroid'],
  Cardiac:   ['troponin', 'ck-mb', 'bnp', 'nt-probnp', 'creatine kinase', 'ldh', 'homocysteine'],
  Vitamins:  ['vitamin', 'folate', 'ferritin', 'iron', 'b12', 'b9', 'd3', '25-oh'],
  Other:     [],
};

function categorise(testName) {
  const lower = (testName || '').toLowerCase();
  for (const [cat, keywords] of Object.entries(CATEGORY_KEYWORDS)) {
    if (cat === 'Other') continue;
    if (keywords.some((k) => lower.includes(k))) return cat;
  }
  return 'Other';
}

// ── ReferenceBar ─────────────────────────────────────────────────────────────
export function ReferenceBar({ value, low, high }) {
  const range = high - low;
  const padding = range * 0.5;
  const min = low - padding;
  const max = high + padding;
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));
  const lowPct = ((low - min) / (max - min)) * 100;
  const highPct = ((high - min) / (max - min)) * 100;
  const isHigh = value > high;
  const isLow = value < low;
  return (
    <div className="relative h-2 bg-gray-200 rounded-full w-full">
      <div
        className="absolute h-full bg-green-300 rounded-full"
        style={{ left: `${lowPct}%`, width: `${highPct - lowPct}%` }}
      />
      <div
        className={`absolute -top-1 w-4 h-4 rounded-full border-2 border-white shadow ${
          isHigh ? 'bg-red-500' : isLow ? 'bg-amber-500' : 'bg-green-500'
        }`}
        style={{ left: `calc(${pct}% - 8px)` }}
      />
    </div>
  );
}

// ── Parse "low – high" from range string ─────────────────────────────────────
function parseRange(rangeStr) {
  if (!rangeStr) return null;
  const m = rangeStr.match(/([\d.]+)\s*[-–]\s*([\d.]+)/);
  if (!m) return null;
  return { low: parseFloat(m[1]), high: parseFloat(m[2]) };
}

// ── Status badge ─────────────────────────────────────────────────────────────
function StatusBadge({ status, darkMode }) {
  const cfg = {
    High:   darkMode ? 'bg-red-950/80 text-red-300 border-red-900'     : 'bg-red-50 text-red-700 border-red-200',
    Low:    darkMode ? 'bg-amber-950/80 text-amber-300 border-amber-900' : 'bg-amber-50 text-amber-700 border-amber-200',
    Normal: darkMode ? 'bg-emerald-950/80 text-emerald-300 border-emerald-900' : 'bg-emerald-50 text-emerald-700 border-emerald-200',
  };
  const cls = cfg[status] ?? (darkMode ? 'bg-zinc-800 text-zinc-300 border-zinc-700' : 'bg-zinc-100 text-zinc-600 border-zinc-200');
  return (
    <span className={`px-2.5 py-0.5 rounded-md text-[10px] font-semibold border ${cls}`}>
      {status || 'Extracted'}
    </span>
  );
}

// ── Category panel ────────────────────────────────────────────────────────────
function CategoryPanel({ category, rows, darkMode, defaultOpen }) {
  const [open, setOpen] = useState(defaultOpen);
  const abnormalCount = rows.filter((r) => r.status === 'High' || r.status === 'Low').length;

  const cardBg     = darkMode ? 'bg-[#121212]' : 'bg-white';
  const cardBorder = darkMode ? 'border-zinc-800' : 'border-zinc-200';
  const textPrimary   = darkMode ? 'text-white'    : 'text-zinc-900';
  const textSecondary = darkMode ? 'text-zinc-400' : 'text-zinc-500';

  return (
    <div className={`rounded-2xl overflow-hidden border mb-3 ${cardBg} ${cardBorder}`}>
      <button
        onClick={() => setOpen((v) => !v)}
        className={`w-full flex items-center justify-between px-4 py-3 text-sm font-semibold transition-colors ${
          darkMode ? 'hover:bg-zinc-900/60' : 'hover:bg-zinc-50'
        }`}
      >
        <div className="flex items-center gap-2">
          <span className={textPrimary}>{category}</span>
          <span className={`text-[11px] font-normal ${textSecondary}`}>{rows.length} test{rows.length !== 1 ? 's' : ''}</span>
          {abnormalCount > 0 && (
            <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-red-500/10 text-red-500 border border-red-500/20">
              {abnormalCount} abnormal
            </span>
          )}
        </div>
        {open ? <ChevronUp className="w-4 h-4 text-zinc-400" /> : <ChevronDown className="w-4 h-4 text-zinc-400" />}
      </button>

      {open && (
        <div className={`border-t ${cardBorder}`}>
          <table className="w-full text-left text-xs">
            <thead className={`${darkMode ? 'bg-zinc-900 text-zinc-400' : 'bg-zinc-50 text-zinc-500'}`}>
              <tr>
                <th className="p-3 px-4 font-semibold">Test Name</th>
                <th className="p-3 px-4 font-semibold">Value</th>
                <th className="p-3 px-4 font-semibold hidden sm:table-cell">Reference Range</th>
                <th className="p-3 px-4 font-semibold hidden md:table-cell">Range Bar</th>
                <th className="p-3 px-4 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className={`divide-y ${darkMode ? 'divide-zinc-800/80' : 'divide-zinc-100'}`}>
              {rows.map((row, idx) => {
                const parsed = parseRange(row.range);
                const numVal = parseFloat(row.value);
                return (
                  <tr key={idx} className={`transition-colors ${darkMode ? 'hover:bg-zinc-900/50' : 'hover:bg-zinc-50'}`}>
                    <td className={`p-3 px-4 font-medium ${textPrimary}`}>{row.test}</td>
                    <td className={`p-3 px-4 font-semibold ${textPrimary}`}>
                      {row.value}{' '}
                      <span className={`text-[11px] font-normal ${textSecondary}`}>{row.unit}</span>
                    </td>
                    <td className={`p-3 px-4 hidden sm:table-cell ${textSecondary}`}>{row.range || 'N/A'}</td>
                    <td className="p-3 px-4 hidden md:table-cell w-36">
                      {parsed && !isNaN(numVal) ? (
                        <ReferenceBar value={numVal} low={parsed.low} high={parsed.high} />
                      ) : (
                        <span className={`text-[11px] ${textSecondary}`}>—</span>
                      )}
                    </td>
                    <td className="p-3 px-4">
                      <StatusBadge status={row.status} darkMode={darkMode} />
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

// ── CSV export ────────────────────────────────────────────────────────────────
export function exportMetricsCsv(metrics) {
  const header = ['Test', 'Value', 'Unit', 'Reference Range', 'Status', 'Category'];
  const rows = metrics.map((m) => [
    m.test ?? '',
    m.value ?? '',
    m.unit ?? '',
    m.range ?? '',
    m.status ?? '',
    categorise(m.test),
  ]);
  const csv = [header, ...rows]
    .map((r) => r.map((cell) => `"${String(cell).replace(/"/g, '""')}"`).join(','))
    .join('\n');
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'lab_metrics.csv';
  a.click();
  URL.revokeObjectURL(url);
}

// ── Main LabMetrics component ─────────────────────────────────────────────────
export default function LabMetrics({ metrics = [], darkMode, onBack }) {
  const [search, setSearch] = useState('');
  const [activeCategory, setActiveCategory] = useState(null);

  const textPrimary   = darkMode ? 'text-white'    : 'text-zinc-900';
  const textSecondary = darkMode ? 'text-zinc-400' : 'text-zinc-500';

  // Abnormal-first sort
  const sorted = useMemo(() => {
    const order = { High: 0, Low: 1, Normal: 2 };
    return [...metrics].sort((a, b) => (order[a.status] ?? 3) - (order[b.status] ?? 3));
  }, [metrics]);

  // Search + category filter
  const filtered = useMemo(() => {
    let result = sorted;
    if (search.trim()) {
      const q = search.toLowerCase();
      result = result.filter((m) => (m.test || '').toLowerCase().includes(q));
    }
    if (activeCategory) {
      result = result.filter((m) => categorise(m.test) === activeCategory);
    }
    return result;
  }, [sorted, search, activeCategory]);

  // Group by category
  const grouped = useMemo(() => {
    const map = {};
    for (const row of filtered) {
      const cat = categorise(row.test);
      if (!map[cat]) map[cat] = [];
      map[cat].push(row);
    }
    return map;
  }, [filtered]);

  const categories = Object.keys(grouped);
  const allCategories = [...new Set(sorted.map((m) => categorise(m.test)))];

  return (
    <div className="animate-fade-in py-4">
      {/* Header row */}
      <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
        <div>
          <h2 className={`text-xl font-bold tracking-tight ${textPrimary}`}>Structured Lab Metrics</h2>
          <p className={`text-xs mt-0.5 ${textSecondary}`}>
            {metrics.length} tests extracted • abnormal values shown first
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => exportMetricsCsv(metrics)}
            className={`px-3 py-1.5 rounded-xl text-xs flex items-center gap-1.5 border transition-colors ${
              darkMode
                ? 'bg-zinc-900 hover:bg-zinc-800 text-zinc-200 border-zinc-800'
                : 'bg-white hover:bg-zinc-50 text-zinc-700 border-zinc-200'
            }`}
            aria-label="Export CSV"
          >
            <Download className="w-3.5 h-3.5" />
            <span>Export CSV</span>
          </button>
          {onBack && (
            <button
              onClick={onBack}
              className={`text-xs underline ${darkMode ? 'text-zinc-400 hover:text-white' : 'text-zinc-500 hover:text-zinc-900'}`}
            >
              Back to Chat →
            </button>
          )}
        </div>
      </div>

      {/* Search */}
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

      {/* Category filter chips */}
      {allCategories.length > 1 && (
        <div className="flex flex-wrap gap-2 mb-4">
          <button
            onClick={() => setActiveCategory(null)}
            className={`px-3 py-1 rounded-full text-[11px] font-medium border transition-colors ${
              !activeCategory
                ? darkMode ? 'bg-zinc-100 text-black border-zinc-100' : 'bg-zinc-900 text-white border-zinc-900'
                : darkMode ? 'border-zinc-700 text-zinc-400 hover:border-zinc-500' : 'border-zinc-300 text-zinc-600 hover:border-zinc-400'
            }`}
          >
            All
          </button>
          {allCategories.map((cat) => (
            <button
              key={cat}
              onClick={() => setActiveCategory(activeCategory === cat ? null : cat)}
              className={`px-3 py-1 rounded-full text-[11px] font-medium border transition-colors ${
                activeCategory === cat
                  ? darkMode ? 'bg-zinc-100 text-black border-zinc-100' : 'bg-zinc-900 text-white border-zinc-900'
                  : darkMode ? 'border-zinc-700 text-zinc-400 hover:border-zinc-500' : 'border-zinc-300 text-zinc-600 hover:border-zinc-400'
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      )}

      {/* Category panels */}
      {categories.length === 0 ? (
        <p className={`text-sm text-center py-8 ${textSecondary}`}>No tests match your search.</p>
      ) : (
        categories.map((cat) => (
          <CategoryPanel
            key={cat}
            category={cat}
            rows={grouped[cat]}
            darkMode={darkMode}
            defaultOpen={true}
          />
        ))
      )}
    </div>
  );
}
