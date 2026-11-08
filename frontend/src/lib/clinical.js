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

/** Extract the first number from a value string ("14.2", "<5", "1,234 cells"). */
export function parseNumeric(value) {
  if (value === null || value === undefined) return null;
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  const s = String(value);
  if (/^\s*\d+\s*:\s*\d+/.test(s)) return null;
  const match = s.replace(/−/g, '-').match(NUM_RE);
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
  const s = String(range).replace(/−/g, '-').replace(/,/g, '').trim();
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
  if (s.includes('critical') || s.includes('panic')) return 'critical';
  if (s.includes('border')) return 'borderline';
  if (s === 'high' || s.startsWith('high') || s.includes('elevated') || s === 'h') return 'high';
  if (s === 'low' || s.startsWith('low') || s.includes('deficien') || s === 'l') return 'low';
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
    if (!s && parseNumeric(row?.value) === null) return 'unknown';
    return s ? 'unknown' : 'normal';
  }
  if (pos.side === 'above') return 'high';
  if (pos.side === 'below') return 'low';
  return pos.nearEdge ? 'borderline' : 'normal';
}

export function isFlagged(row) {
  const c = classifyStatus(row);
  return c === 'critical' || c === 'high' || c === 'low' || c === 'borderline';
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
  rose: { text: 'text-rose-300', bg: 'bg-rose-500/10', border: 'border-rose-500/25', dot: 'bg-rose-500', hex: '#f43f5e' },
  amber: { text: 'text-amber-300', bg: 'bg-amber-500/10', border: 'border-amber-500/25', dot: 'bg-amber-500', hex: '#f59e0b' },
  emerald: { text: 'text-emerald-300', bg: 'bg-emerald-500/10', border: 'border-emerald-500/25', dot: 'bg-emerald-500', hex: '#10b981' },
  cyan: { text: 'text-cyan-300', bg: 'bg-cyan-500/10', border: 'border-cyan-500/25', dot: 'bg-cyan-500', hex: '#06b6d4' },
  neutral: { text: 'text-slate-300', bg: 'bg-slate-500/10', border: 'border-slate-500/25', dot: 'bg-slate-400', hex: '#94a3b8' },
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
  { key: 'glycemic', label: 'Metabolic & Glycemic', match: /(hba1c|\ba1c\b|glucose|sugar|insulin|homa|fbs|ppbs|fructosamine|glycated)/i },
  { key: 'lipids', label: 'Lipids', match: /(cholesterol|\bldl\b|\bhdl\b|vldl|triglycer|\btg\b|lipoprotein|\bapo|lp\(a\)|non.?hdl)/i },
  { key: 'thyroid', label: 'Thyroid & Vitamins', match: /(\btsh\b|\bt3\b|\bt4\b|ft3|ft4|thyro|vitamin|\bb12\b|cobalamin|folate|folic|25.?oh|calcidiol|\bd3\b)/i },
  { key: 'renal', label: 'Renal & Electrolytes', match: /(creatinine|\burea\b|\bbun\b|egfr|\bgfr\b|uric|sodium|\bna\b|potassium|\bk\b|chloride|bicarbonate|\bco2\b|calcium|phosph|magnesium|microalbumin|albumin.?creatinine|\bacr\b|cystatin|osmolal)/i },
  { key: 'hepatic', label: 'Hepatic', match: /(\balt\b|sgpt|\bast\b|sgot|alkaline|\balp\b|bilirubin|\bggt\b|gamma|albumin|globulin|total protein|a\/g|\bldh\b)/i },
  { key: 'hematology', label: 'Hematology & Iron', match: /(hemoglobin|haemoglobin|\bhgb\b|\bhb\b|\brbc\b|\bwbc\b|platelet|\bplt\b|hematocrit|haematocrit|\bhct\b|\bpcv\b|\bmcv\b|\bmch\b|mchc|\brdw\b|neutrophil|lymphocyte|monocyte|eosinophil|basophil|\besr\b|ferritin|\biron\b|tibc|transferrin|reticulocyte|leukocyte|erythrocyte)/i },
  { key: 'inflammation', label: 'Inflammation & Immunity', match: /(\bcrp\b|hs.?crp|c.?reactive|procalcitonin|\bil.?6\b|rheumatoid|\bana\b|immunoglobulin|\bige\b)/i },
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

  const flagged = counts.critical + counts.high + counts.low + counts.borderline;
  return { ...counts, flagged, inRange: counts.normal, systems };
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

