/**
 * Clinical computation helpers.
 *
 * Everything in here is a pure function over the `lab_metrics` rows returned by
 * POST /extract-metrics, so every visualization (range bars, triage summary,
 * organ-system grouping, longitudinal trends) works client-side today, with no
 * new backend endpoint required.
 *
 * Metric row shape (backend contract, all fields optional except name/value):
 *   { test | name, value, unit, range | reference_range, status,
 *     previous_value, previous_date, delta_abs, delta_pct, delta_alert }
 */

// ── Primitive parsing ────────────────────────────────────────────────────────

const NUM_RE = /-?\d[\d,]*\.?\d*|-?\.\d+/;

/** Extract the first number from a value string ("14.2", "<5", "1,234 cells", "2,38,000", "< 0.5"). */
export function parseNumeric(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  let s = String(value);
  if (/\b\d+\s*:\s*\d+\b/.test(s)) return null;
  if (/^\s*(positive|negative|reactive|non[-\s]?reactive|detected|absent|trace|nil)\b/i.test(s)) return null;
  s = s.replace(/−/g, '-');

  // Strip leading comparator (< 0.5 -> 0.5, > 60 -> 60)
  s = s.replace(/^[<>≤≥=\s]+/, '').trim();

  // Normalize grouping commas vs decimal commas (handles 150,000, 2,38,000, 4,500.50, 3,9)
  if (s.includes('.') && s.includes(',')) {
    if (s.lastIndexOf(',') < s.lastIndexOf('.')) {
      s = s.replace(/,/g, '');
    } else {
      s = s.replace(/\./g, '').replace(/,/g, '.');
    }
  } else if ((s.match(/,/g) || []).length > 1) {
    s = s.replace(/,/g, '');
  } else if (s.includes(',')) {
    if (/,\d{3}\b/.test(s)) {
      s = s.replace(/,/g, '');
    } else if (/,\d{1,2}\b/.test(s)) {
      s = s.replace(/,/g, '.');
    }
  }

  const match = s.match(NUM_RE);
  if (!match) return null;
  const n = parseFloat(match[0].replace(/,/g, ''));
  return Number.isFinite(n) ? n : null;
}

/**
 * Parse a reference interval string.
 * Supports "12–17", "12 - 17", "0.4 to 4.0", "<200", "≤ 5.7", ">40", "≥ 60",
 * "Up to 35", "Above 40". Returns { low, high, kind } or null.
 */
export function parseRange(range) {
  if (range === null || range === undefined) return null;
  let s = String(range)
    .replace(/−/g, '-')
    .replace(/(\d),(\d{3})\b/g, '$1$2')
    .replace(/(\d),(\d{1,2})(?!\d)/g, '$1.$2')
    .replace(/,/g, '')
    .trim();
  if (!s || s === '—' || s === '-') return null;

  // Multi-tier & sex/pregnancy qualifiers guard
  if (/(\bmale\b|\bfemale\b|\bmen\b|\bwomen\b|pregnan|trimester)/i.test(s)) return null;
  const intervalMatches = s.match(/-?\d+(?:\.\d+)?\s*(?:-|–|—|\bto\b)\s*-?\d+(?:\.\d+)?/gi);
  if (intervalMatches && intervalMatches.length > 1) return null;

  const between = s.match(/(-?\d*\.?\d+)\s*(?:-|–|—|to)\s*(-?\d*\.?\d+)/i);
  if (between) {
    const a = parseFloat(between[1]);
    const b = parseFloat(between[2]);
    if (Number.isFinite(a) && Number.isFinite(b)) {
      return { low: Math.min(a, b), high: Math.max(a, b), kind: 'between' };
    }
  }

  const upper = s.match(/(?:<|≤|=<|<=|up\s*to|below|less\s*than)\s*(-?\d*\.?\d+)/i);
  if (upper) {
    const h = parseFloat(upper[1]);
    if (Number.isFinite(h)) return { low: null, high: h, kind: 'upper' };
  }

  const lower = s.match(/(?:>|≥|=>|>=|above|greater\s*than|more\s*than)\s*(-?\d*\.?\d+)/i);
  if (lower) {
    const l = parseFloat(lower[1]);
    if (Number.isFinite(l)) return { low: l, high: null, kind: 'lower' };
  }

  return null;
}

/** Best-effort date parser for "24 Oct 2026", "2026-10-24", "24/10/2026". */
export function parseClinicalDate(input) {
  if (!input) return null;
  if (input instanceof Date) return Number.isNaN(input.getTime()) ? null : input.getTime();
  const s = String(input).trim();

  // Date-only ISO → local midnight (Date.parse would use UTC and shift the day)
  const ymd = s.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (ymd) {
    const d = new Date(Number(ymd[1]), Number(ymd[2]) - 1, Number(ymd[3]));
    return Number.isNaN(d.getTime()) ? null : d.getTime();
  }

  const dmy = s.match(/^(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})$/);
  if (dmy) {
    const p1 = Number(dmy[1]);
    const p2 = Number(dmy[2]);
    const year = Number(dmy[3]);
    let day, month;
    if (p1 > 12 && p2 <= 12) {
      day = p1;
      month = p2;
    } else if (p2 > 12 && p1 <= 12) {
      month = p1;
      day = p2;
    } else {
      day = p1;
      month = p2;
    }
    if (month < 1 || month > 12 || day < 1 || day > 31) return null;
    const d = new Date(year, month - 1, day);
    if (Number.isNaN(d.getTime())) return null;
    if (d.getFullYear() !== year || d.getMonth() !== month - 1 || d.getDate() !== day) {
      return null;
    }
    return d.getTime();
  }

  const parsed = Date.parse(s);
  if (!Number.isNaN(parsed)) return parsed;

  const loose = Date.parse(s.replace(/(\d+)(st|nd|rd|th)/, '$1'));
  return Number.isNaN(loose) ? null : loose;
}

export function formatShortDate(ts) {
  if (ts === null || ts === undefined) return '';
  const d = new Date(ts);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
}

// ── Row accessors ────────────────────────────────────────────────────────────

export const metricName = (row) => String(row?.test || row?.name || '—').replace(/\*\*/g, '').trim();
export const metricRange = (row) => row?.range || row?.reference_range || '';
export const metricKey = (row) => normalizeName(metricName(row));

export function normalizeName(name) {
  return String(name || '')
    .toLowerCase()
    .replace(/\(.*?\)/g, '')
    .replace(/[^a-z0-9]+/g, '')
    .trim();
}

/** Δ% for a row: backend `delta_pct` first, then computed from previous_value. */
export function deltaPct(row) {
  if (row?.delta_pct !== null && row?.delta_pct !== undefined && row?.delta_pct !== '') {
    const n = parseNumeric(row.delta_pct);
    if (n !== null) return n;
  }
  const cur = parseNumeric(row?.value);
  const prev = parseNumeric(row?.previous_value);
  if (cur === null || prev === null || prev === 0) return null;
  return Math.round(((cur - prev) / Math.abs(prev)) * 1000) / 10;
}

export const NOTABLE_DELTA_PCT = 10;

export function isNotableShift(row) {
  if (row?.delta_alert) return true;
  const d = deltaPct(row);
  return d !== null && Math.abs(d) >= NOTABLE_DELTA_PCT;
}

export function isNotableDrop(row) {
  if (row?.delta_alert && /drop|decreas|fall/i.test(row.delta_alert)) return true;
  const d = deltaPct(row);
  return d !== null && d <= -NOTABLE_DELTA_PCT;
}

// ── Status classification ────────────────────────────────────────────────────

/**
 * Returns one of: 'critical' | 'high' | 'low' | 'borderline' | 'normal' | 'unknown'.
 * Trusts the backend status label, except that a 'Normal' label is overridden when the value is clearly outside a parseable reference range.
 */
export function classifyStatus(row) {
  const s = String(row?.status || '').trim().toLowerCase();
  if (s === 'unknown') return 'unknown';
  if (s === 'high-normal' || s === 'low-normal') return 'normal';
  if (s.includes('critical') || s.includes('panic')) return 'critical';
  if (s.includes('border')) return 'borderline';
  if (s === 'high' || s.startsWith('high') || s.includes('elevated') || s === 'h') return 'high';
  if (s === 'low' || s.startsWith('low') || s.includes('deficien') || s === 'l') return 'low';

  const valTrimmed = String(row?.value || '').trim();
  const rangeTrimmed = String(row?.range || row?.reference_range || '').trim();

  // Qualitative serology (e.g. Positive vs Negative)
  if (/^\s*(negative|non[-\s]?reactive|absent|nil)\s*$/i.test(rangeTrimmed)) {
    if (/^\s*(negative|non[-\s]?reactive|absent|nil|none\s+detected)\s*$/i.test(valTrimmed)) {
      return 'normal';
    }
    if (
      /\b(positive|reactive|detected|present)\b/i.test(valTrimmed) &&
      !/\b(non[-\s]?reactive|negative)\b/i.test(valTrimmed)
    ) {
      return 'high';
    }
  }

  // Comparator values (> 200, < 0.5)
  if (/^>=?/.test(valTrimmed)) {
    const v = parseNumeric(row?.value);
    const r = parseRange(row?.range || row?.reference_range);
    if (v !== null && r?.high !== null && v >= r.high) return 'high';
  }
  if (/^<=?/.test(valTrimmed)) {
    const v = parseNumeric(row?.value);
    const r = parseRange(row?.range || row?.reference_range);
    if (v !== null && r?.low !== null && r.low > 0 && v <= r.low) return 'low';
  }

  if (s === 'abnormal') {
    const pos = rangeGeometry(row);
    if (pos?.side === 'above') return 'high';
    if (pos?.side === 'below') return 'low';
    return 'high';
  }
  if (s === 'normal' || s.includes('optimal') || s.includes('within') || s === 'in range') {
    const pos = rangeGeometry(row);
    if (pos?.side === 'above') return 'high';   // label says normal, numbers disagree
    if (pos?.side === 'below') return 'low';
    return 'normal';
  }

  const pos = rangeGeometry(row);
  if (!pos) {
    if (s) return 'unknown';
    if (rangeTrimmed) return 'unknown';
    if (parseNumeric(row?.value) === null) return 'unknown';
    return 'normal';
  }
  if (pos.side === 'above') return 'high';
  if (pos.side === 'below') return 'low';
  return pos.nearEdge ? 'borderline' : 'normal';
}

export function isFlagged(row) {
  const c = classifyStatus(row);
  return c === 'critical' || c === 'high' || c === 'low' || c === 'abnormal';
}

/** Semantic tone per the MediSkye clinical palette. */
export function statusTone(row) {
  const c = classifyStatus(row);
  if (c === 'critical' || c === 'high') return 'rose';
  if (c === 'low' || c === 'borderline') return 'amber';
  if (isNotableShift(row)) return 'amber';
  if (c === 'normal') return 'emerald';
  return 'neutral';
}

export const TONE = {
  rose: { text: 'text-rose-700', bg: 'bg-rose-50', border: 'border-rose-200', dot: 'bg-rose-600', hex: '#be123c' },
  amber: { text: 'text-amber-700', bg: 'bg-amber-50', border: 'border-amber-200', dot: 'bg-amber-600', hex: '#b45309' },
  emerald: { text: 'text-emerald-700', bg: 'bg-emerald-50', border: 'border-emerald-200', dot: 'bg-emerald-600', hex: '#047857' },
  cyan: { text: 'text-cyan-800', bg: 'bg-cyan-50', border: 'border-cyan-200', dot: 'bg-cyan-600', hex: '#0e7490' },
  neutral: { text: 'text-slate-700', bg: 'bg-slate-500/10', border: 'border-slate-200', dot: 'bg-slate-500', hex: '#475569' },
};

// ── Range geometry ───────────────────────────────────────────────────────────

/**
 * Compute where a value sits relative to its reference interval on a padded
 * linear scale. All percentages are 0–100 along the bar.
 *
 * Returns null when either the value or the range can't be parsed.
 */
export function rangeGeometry(row, valueOverride) {
  const value = valueOverride !== undefined ? valueOverride : parseNumeric(row?.value);
  const range = parseRange(metricRange(row));
  if (value === null || !range) return null;
  return geometryFor(value, range);
}

export function geometryFor(value, range) {
  let { low, high } = range;
  let domainMin;
  let domainMax;

  if (range.kind === 'between') {
    const span = Math.max(high - low, Math.abs(high) * 0.05, 1e-6);
    const pad = span * 0.45;
    domainMin = Math.min(low - pad, value - span * 0.08);
    domainMax = Math.max(high + pad, value + span * 0.08);
    if (low >= 0 && domainMin < 0) domainMin = 0;
  } else if (range.kind === 'upper') {
    low = 0;
    domainMin = 0;
    domainMax = Math.max(high * 1.45, value * 1.08, 1e-6);
  } else {
    high = null;
    domainMin = 0;
    domainMax = Math.max(low * 1.9, value * 1.12, 1e-6);
  }

  const span = domainMax - domainMin || 1;
  const toPct = (v) => Math.min(100, Math.max(0, ((v - domainMin) / span) * 100));

  const lowPct = toPct(low ?? domainMin);
  const highPct = high === null ? 100 : toPct(high);
  const valuePct = toPct(value);

  let side = 'inside';
  if (high !== null && value > high) side = 'above';
  else if (low !== null && value < low) side = 'below';

  // Within 7% of interval width from an edge → borderline
  let nearEdge = false;
  if (side === 'inside' && range.kind === 'between') {
    const width = high - low;
    nearEdge = width > 0 && (value - low < width * 0.07 || high - value < width * 0.07);
  }

  // Position inside the interval (0 = bottom edge, 1 = top edge)
  let withinFraction = null;
  if (range.kind === 'between' && high > low) withinFraction = (value - low) / (high - low);

  return { value, low, high, kind: range.kind, domainMin, domainMax, lowPct, highPct, valuePct, side, nearEdge, withinFraction };
}

/** Plain-language placement, e.g. "Near the bottom of 200–900". */
export function describePlacement(row) {
  const g = rangeGeometry(row);
  if (!g) return null;
  const r = metricRange(row);
  const limit = g.kind === 'between' ? r : `the ${r} limit`;
  if (g.side === 'above') return `Above ${limit}`;
  if (g.side === 'below') return `Below ${limit}`;
  if (g.withinFraction === null) return `Within ${r}`;
  if (g.withinFraction < 0.2) return `Near the bottom of ${r}`;
  if (g.withinFraction > 0.8) return `Near the top of ${r}`;
  return `Mid-range of ${r}`;
}

// ── Formatting ───────────────────────────────────────────────────────────────

export function formatDeltaPct(d) {
  if (d === null || d === undefined || Number.isNaN(d)) return '';
  const rounded = Math.abs(d) >= 100 ? Math.round(d) : Math.round(d * 10) / 10;
  return `${rounded > 0 ? '+' : ''}${rounded}%`;
}

export function formatNumber(n, digits = 2) {
  if (n === null || n === undefined || !Number.isFinite(n)) return '—';
  const abs = Math.abs(n);
  const max = abs >= 100 ? 0 : abs >= 10 ? 1 : digits;
  return n.toLocaleString('en-US', { maximumFractionDigits: max });
}

// ── Organ-system grouping ────────────────────────────────────────────────────

export const ORGAN_SYSTEMS = [
  {
    key: 'hematology',
    label: 'Hematology / Blood',
    match: /(hemoglobin|haemoglobin|\bhgb\b|\bhb\b|\brbc\b|\bwbc\b|\btlc\b|leucocyte|leukocyte|\bpcv\b|hematocrit|haematocrit|\bhct\b|\bmcv\b|\bmch\b|mchc|\brdw\b|platelet|\bplt\b|\bmpv\b|neutrophil|\banc\b|lymphocyte|monocyte|eosinophil|\baec\b|basophil|\besr\b|reticulocyte|erythrocyte)/i,
  },
  {
    key: 'glycemic',
    label: 'Metabolic / Glycemic',
    match: /(glucose|\bfbs\b|\bfbg\b|\bppbs\b|\brbs\b|blood sugar|\bsugar\b|hba1c|\ba1c\b|glycated|insulin|c-peptide|c.?peptide|\bhoma\b|lactate|fructosamine)/i,
  },
  {
    key: 'thyroid',
    label: 'Thyroid & Endocrine / Hormones',
    match: /(anti.?tpo|anti.?tg|thyroglobulin|\btsh\b|thyroid|thyro|\bt3\b|\bt4\b|ft3|ft4|cortisol|\bacth\b|testosterone|estradiol|estrogen|progesterone|prolactin|\bfsh\b|\blh\b|\bdhea\b|\bshbg\b|\bpsa\b|\bpth\b|parathyroid)/i,
  },
  {
    key: 'lipids',
    label: 'Lipids & Cardiovascular',
    match: /(cholesterol|triglyceride|triglycer|\btg\b|\bhdl\b|\bldl\b|vldl|non.?hdl|apob|\bapo\s*b\b|\bapo\s*a\b|\bapo\b|lipoprotein|lp\(a\)|troponin|\bbnp\b|nt.?probnp|ck.?mb|homocysteine)/i,
  },
  {
    key: 'hepatic',
    label: 'Liver / Hepatic',
    match: /(\bast\b|sgot|\balt\b|sgpt|\balp\b|alkaline phosphatase|alkaline|\bggt\b|gamma\s*gt|gamma|bilirubin|albumin|globulin|total protein|a\/g ratio|a\/g|ammonia|\bldh\b)/i,
  },
  {
    key: 'renal',
    label: 'Kidney / Renal & Electrolytes',
    match: /(creatinine|\bbun\b|\burea\b|egfr|\bgfr\b|uric acid|uric|urate|cystatin|uacr|microalbumin|albumin.?creatinine|\bacr\b|sodium|\bna\b|potassium|\bk\b|chloride|bicarbonate|\bhco3\b|\bco2\b|calcium|magnesium|phosphorus|phosphate|phosph|osmolal)/i,
  },
  {
    key: 'vitamins',
    label: 'Vitamins, Iron & Nutrition',
    match: /(vitamin|vit\s*d|vit\s*b12|\bb12\b|cobalamin|folate|folic|ferritin|\biron\b|tibc|uibc|transferrin|tsat|zinc|copper|\bmma\b|methylmalonic|25.?oh|calcidiol|\bd3\b)/i,
  },
  {
    key: 'inflammation',
    label: 'Inflammation, Immunology & Coagulation',
    match: /(\bcrp\b|hs.?crp|c.?reactive|\bana\b|rheumatoid|anti.?ccp|\bige\b|\bigg\b|\biga\b|\bigm\b|immunoglobulin|complement|\bpt\b|\binr\b|prothrombin|\baptt\b|d.?dimer|hbsag|\bhcv\b|\bhiv\b|vdrl|widal|dengue|procalcitonin|\bil.?6\b)/i,
  },
];

export const OTHER_SYSTEM = { key: 'other', label: 'Other markers' };

export function organSystemOf(row) {
  const name = metricName(row);
  const hit = ORGAN_SYSTEMS.find((s) => s.match.test(name));
  return hit || OTHER_SYSTEM;
}

/** Severity rank used for "flagged first" ordering. Lower = more urgent. */
export function severityRank(row) {
  const c = classifyStatus(row);
  if (c === 'critical') return 0;
  if (c === 'high') return 1;
  if (c === 'low') return 2;
  if (c === 'borderline') return 3;
  if (isNotableShift(row)) return 4;
  return 5;
}

/** Legacy ordering contract: any abnormal / delta-alert row before Normal rows (stable). */
export function sortFlaggedFirst(metrics) {
  if (!Array.isArray(metrics)) return [];
  const priority = (m) => {
    const s = String(m?.status || '').trim().toLowerCase();
    if (s === 'high' || s === 'low' || s === 'critical' || s === 'abnormal' || m?.delta_alert || isFlagged(m)) return 0;
    return 1;
  };
  return metrics
    .map((m, i) => ({ m, i }))
    .sort((a, b) => priority(a.m) - priority(b.m) || severityRank(a.m) - severityRank(b.m) || a.i - b.i)
    .map(({ m }) => m);
}

/** Aggregate triage summary across all metrics. */
export function summarizeTriage(metrics) {
  const list = Array.isArray(metrics) ? metrics.filter(Boolean) : [];
  const counts = { total: list.length, critical: 0, high: 0, low: 0, borderline: 0, normal: 0, unknown: 0, shifts: 0, drops: 0 };
  const systemMap = new Map();

  list.forEach((row) => {
    const c = classifyStatus(row);
    counts[c] = (counts[c] || 0) + 1;
    if (isNotableShift(row)) counts.shifts += 1;
    if (isNotableDrop(row)) counts.drops += 1;

    const sys = organSystemOf(row);
    if (!systemMap.has(sys.key)) systemMap.set(sys.key, { key: sys.key, label: sys.label, metrics: [], flagged: 0, shifts: 0, worst: 5 });
    const entry = systemMap.get(sys.key);
    entry.metrics.push(row);
    if (isFlagged(row)) entry.flagged += 1;
    if (isNotableShift(row)) entry.shifts += 1;
    entry.worst = Math.min(entry.worst, severityRank(row));
  });

  const order = [...ORGAN_SYSTEMS.map((s) => s.key), OTHER_SYSTEM.key];
  const systems = [...systemMap.values()]
    .map((s) => ({ ...s, metrics: [...s.metrics].sort((a, b) => severityRank(a) - severityRank(b)) }))
    .sort((a, b) => a.worst - b.worst || order.indexOf(a.key) - order.indexOf(b.key));

  const flagged = counts.critical + counts.high + counts.low;
  return { ...counts, flagged, inRange: counts.normal + counts.borderline, systems };
}

export function filterMetrics(metrics, filter) {
  const list = Array.isArray(metrics) ? metrics : [];
  if (filter === 'flagged') return list.filter((m) => isFlagged(m) || Boolean(m?.delta_alert));
  if (filter === 'drops') return list.filter(isNotableDrop);
  if (filter === 'shifts') return list.filter(isNotableShift);
  return list;
}

// ── Longitudinal trends ──────────────────────────────────────────────────────

/**
 * Build per-biomarker time series.
 *
 * @param {Array<{docId, label, date, metrics}>} snapshots  one entry per report
 * @returns {Map<string, {key, name, unit, range, points: Array<{t, value, raw, docId, label, synthetic}>}>}
 *
 * When only one report exists we still produce a 2-point series from the
 * backend's previous_value / previous_date (baseline → follow-up).
 */
export function buildTrendSeries(snapshots) {
  const series = new Map();
  const safeSnapshots = Array.isArray(snapshots) ? snapshots : [];

  const push = (row, point) => {
    const key = metricKey(row);
    if (!key) return;
    if (!series.has(key)) {
      series.set(key, { key, name: metricName(row), unit: row?.unit || '', range: metricRange(row), points: [] });
    }
    const s = series.get(key);
    if (!s.unit && row?.unit) s.unit = row.unit;
    if (!s.range && metricRange(row)) s.range = metricRange(row);
    const dup = s.points.find((p) => p.t === point.t && p.value === point.value);
    if (!dup) s.points.push(point);
  };

  safeSnapshots.forEach((snap, idx) => {
    const rows = Array.isArray(snap?.metrics) ? snap.metrics : [];
    const snapT = parseClinicalDate(snap?.date) ?? parseClinicalDate(rows.collected_at) ?? idx;
    rows.forEach((row) => {
      const v = parseNumeric(row?.value);
      if (v === null) return;
      push(row, { t: snapT, value: v, raw: row.value, docId: snap.docId, label: snap.label, status: classifyStatus(row), synthetic: false });

      const pv = parseNumeric(row?.previous_value);
      if (pv !== null) {
        const pt = parseClinicalDate(row?.previous_date);
        const hasParsedDate = pt !== null;
        const THIRTY_DAYS = 30 * 24 * 60 * 60 * 1000;
        const t = hasParsedDate
          ? pt
          : (typeof snapT === 'number' && snapT > 1e9 ? snapT - THIRTY_DAYS : (typeof snapT === 'number' ? snapT - 1 : idx - 0.5));
        push(row, { t, value: pv, raw: row.previous_value, docId: null, label: row.previous_date || 'Baseline', status: null, synthetic: true, hasParsedDate });
      }
    });
  });

  series.forEach((s) => {
    s.points.sort((a, b) => a.t - b.t);
    // A reconstructed baseline is redundant when a real reading exists within ~1.5 days of it
    const DAY = 36 * 60 * 60 * 1000;
    s.points = s.points.filter((p, i, arr) => !(p.synthetic && p.hasParsedDate && arr.some((q, j) => j !== i && !q.synthetic && Math.abs(q.t - p.t) <= DAY)));
    const first = s.points[0];
    const last = s.points[s.points.length - 1];
    s.change = first && last && first !== last && first.value !== 0
      ? Math.round(((last.value - first.value) / Math.abs(first.value)) * 1000) / 10
      : null;
  });

  return series;
}

/** Order trend series: most-moved & flagged biomarkers first. */
export function rankTrendSeries(seriesMap, latestMetrics = []) {
  const latestByKey = new Map((latestMetrics || []).map((m) => [metricKey(m), m]));
  return [...seriesMap.values()]
    .filter((s) => s.points.length >= 1)
    .sort((a, b) => {
      const ra = latestByKey.has(a.key) ? severityRank(latestByKey.get(a.key)) : 5;
      const rb = latestByKey.has(b.key) ? severityRank(latestByKey.get(b.key)) : 5;
      if (ra !== rb) return ra - rb;
      const multiA = a.points.length > 1 ? 1 : 0;
      const multiB = b.points.length > 1 ? 1 : 0;
      if (multiA !== multiB) return multiB - multiA;
      return Math.abs(b.change || 0) - Math.abs(a.change || 0);
    });
}

/** Human label for a report used in pickers and chips. */
export function reportLabel(doc) {
  if (!doc) return 'Lab report';
  const base = doc.title || doc.name || doc.filename || 'Lab report';
  return String(base).replace(/\.pdf$/i, '');
}

export function reportDateLabel(doc) {
  if (!doc) return '';
  if (doc.collected_at) return String(doc.collected_at);
  const t = parseClinicalDate(doc.created_at);
  return t ? formatShortDate(t) : '';
}

/** Convert weight strings like "175 lb", "175 lbs", "80 kg", "75" to standard kg string. */
export function parseWeightToKgString(input) {
  if (input === null || input === undefined) return '';
  const s = String(input).trim();
  if (!s) return '';
  const match = s.match(/^([\d.]+)\s*(lbs?|pounds?|kg|kgs?|kilograms?)?$/i);
  if (!match) return s;
  const val = parseFloat(match[1]);
  if (isNaN(val)) return s;
  const unit = (match[2] || '').toLowerCase();
  if (unit.startsWith('lb') || unit.startsWith('pound')) {
    const kg = Math.round(val * 0.453592 * 10) / 10;
    return `${kg} kg`;
  }
  return `${val} kg`;
}

/** Strips outer quotation marks only when both the first and last character are quotes. */
export function stripOuterQuotes(str) {
  if (!str || typeof str !== 'string') return '';
  let s = str.trim();
  const QUOTES = ['"', "'", '“', '”', '‘', '’'];
  while (s.length >= 2 && QUOTES.includes(s[0]) && QUOTES.includes(s[s.length - 1])) {
    s = s.slice(1, -1).trim();
  }
  return s;
}

/**
 * Cleanly formats message timestamps to localized short time string (e.g. '09:11 PM'),
 * never letting raw ISO strings or 'Invalid Date' leak to the UI.
 */
export function formatMessageTimestamp(rawTime) {
  if (!rawTime) return 'Just now';
  if (typeof rawTime === 'string') {
    const trimmed = rawTime.trim();
    if (!trimmed || trimmed.toLowerCase() === 'just now' || trimmed.toLowerCase().includes('invalid')) return 'Just now';
    // If it's already a short time format e.g. "09:11 PM", "9:11 AM", "14:30"
    if (/^\d{1,2}:\d{2}(?::\d{2})?(\s*(?:[ap]\.?m\.?))?$/i.test(trimmed)) {
      return trimmed;
    }
    const d = new Date(trimmed);
    if (!isNaN(d.getTime())) {
      try {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      } catch {
        return 'Just now';
      }
    }
    return 'Just now';
  }
  if (rawTime instanceof Date && !isNaN(rawTime.getTime())) {
    try {
      return rawTime.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
      return 'Just now';
    }
  }
  return 'Just now';
}

/**
 * Robust conversation matching across raw IDs, doc_ prefixes, document_ids, and session_ids.
 */
export function isMatchingConversation(c, targetId, docId = null) {
  if (!c || (!targetId && !docId)) return false;
  const cleanTarget = targetId ? String(targetId).replace(/^(?:doc_|session_)/, '') : null;
  const cleanCid = c.id ? String(c.id).replace(/^(?:doc_|session_)/, '') : null;
  const cleanDocId = docId ? String(docId).replace(/^doc_/, '') : null;

  if (targetId && (c.id === targetId || (cleanTarget && cleanCid && cleanCid === cleanTarget))) return true;
  if (cleanTarget && c.session_id && String(c.session_id).replace(/^(?:doc_|session_)/, '') === cleanTarget) return true;
  if (cleanDocId && c.document_id && String(c.document_id).replace(/^doc_/, '') === cleanDocId) return true;
  if (cleanDocId && c.pdf?.id && String(c.pdf.id).replace(/^doc_/, '') === cleanDocId) return true;
  if (cleanTarget && c.document_id && String(c.document_id).replace(/^doc_/, '') === cleanTarget) return true;
  if (cleanTarget && c.pdf?.id && String(c.pdf.id).replace(/^doc_/, '') === cleanTarget) return true;
  return false;
}

/**
 * Single canonical message normalizer:
 * Enforces correct sender/role, unified content/text/message, and clean timestamps.
 */
export function normalizeChatMessage(msg) {
  if (!msg || typeof msg !== 'object') return msg;
  const isUser = msg.sender === 'user' || msg.role === 'user' || msg.type === 'user' || msg.isUser === true;
  const rawText = msg.content ?? msg.text ?? msg.message ?? '';
  const textStr = typeof rawText === 'string' ? rawText : String(rawText || '');
  const timestamp = formatMessageTimestamp(msg.timestamp || msg.created_at);

  return {
    ...msg,
    sender: isUser ? 'user' : (msg.sender === 'assistant' ? 'assistant' : 'ai'),
    role: isUser ? 'user' : 'assistant',
    isUser,
    content: textStr,
    text: textStr,
    message: textStr,
    timestamp,
    created_at: msg.created_at || msg.timestamp || new Date().toISOString(),
  };
}

