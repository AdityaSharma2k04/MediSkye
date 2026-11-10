import { describe, it, expect } from 'vitest';
import {
  parseNumeric,
  parseRange,
  classifyStatus,
  statusTone,
  rangeGeometry,
  describePlacement,
  deltaPct,
  isNotableShift,
  isNotableDrop,
  organSystemOf,
  summarizeTriage,
  sortFlaggedFirst,
  filterMetrics,
  buildTrendSeries,
  parseClinicalDate,
  stripOuterQuotes,
} from '../lib/clinical';

describe('clinical parsing', () => {
  it('parses numeric values with units, commas and comparators', () => {
    expect(parseNumeric('14.2')).toBe(14.2);
    expect(parseNumeric('1,234 cells')).toBe(1234);
    expect(parseNumeric('<5')).toBe(5);
    expect(parseNumeric('1:160')).toBeNull();
    expect(parseNumeric('Positive (1:160)')).toBeNull();
    expect(parseNumeric('n/a')).toBeNull();
  });

  it('parses between / upper / lower reference intervals', () => {
    expect(parseRange('200–900')).toEqual({ low: 200, high: 900, kind: 'between' });
    expect(parseRange('0.4 to 4.0')).toEqual({ low: 0.4, high: 4, kind: 'between' });
    expect(parseRange('<100')).toEqual({ low: null, high: 100, kind: 'upper' });
    expect(parseRange('≥ 60')).toEqual({ low: 60, high: null, kind: 'lower' });
    expect(parseRange('—')).toBeNull();
    expect(parseRange('Male: 13-17, Female: 12-15')).toBeNull();
    expect(parseRange('10-20 to 30-40')).toBeNull();
  });

  it('parses common report date formats', () => {
    expect(parseClinicalDate('24 Oct 2026')).toBe(new Date('24 Oct 2026').getTime());
    expect(new Date(parseClinicalDate('24/10/2026')).getMonth()).toBe(9);
    expect(new Date(parseClinicalDate('10/24/2026')).getMonth()).toBe(9);
    expect(new Date(parseClinicalDate('10/24/2026')).getDate()).toBe(24);
    expect(parseClinicalDate('31/02/2026')).toBeNull();
    expect(parseClinicalDate('')).toBeNull();
  });
});

describe('status, tone and geometry', () => {
  it('trusts backend labels and derives from range when missing', () => {
    expect(classifyStatus({ status: 'High' })).toBe('high');
    expect(classifyStatus({ status: 'Low' })).toBe('low');
    expect(classifyStatus({ status: 'Critical High' })).toBe('critical');
    expect(classifyStatus({ value: '5.9', range: '4.0-5.6' })).toBe('high');
    expect(classifyStatus({ value: '4.8', range: '4.0-5.6' })).toBe('normal');
    expect(classifyStatus({ status: 'Normal', value: '260', range: '0-200' })).toBe('high');
  });

  it('maps tones to the clinical palette (rose high, amber low/shift, emerald normal)', () => {
    expect(statusTone({ status: 'High' })).toBe('rose');
    expect(statusTone({ status: 'Low' })).toBe('amber');
    expect(statusTone({ status: 'Normal', delta_pct: -23 })).toBe('amber');
    expect(statusTone({ status: 'Normal' })).toBe('emerald');
  });

  it('places 238 pg/mL near the bottom of 200–900', () => {
    const row = { test: 'Ferritin', value: '238', range: '200–900', status: 'Normal' };
    const g = rangeGeometry(row);
    expect(g.side).toBe('inside');
    expect(g.valuePct).toBeGreaterThan(g.lowPct);
    expect(g.valuePct).toBeLessThan(g.highPct);
    expect(describePlacement(row)).toBe('Near the bottom of 200–900');
  });

  it('computes Δ% from previous_value when delta_pct is absent', () => {
    const row = { value: '24.0', previous_value: '44.0' };
    expect(deltaPct(row)).toBe(-45.5);
    expect(isNotableShift(row)).toBe(true);
    expect(isNotableDrop(row)).toBe(true);
    expect(isNotableShift({ value: '105', previous_value: '100' })).toBe(false);
  });
});

describe('grouping, triage and trends', () => {
  const metrics = [
    { test: 'Hemoglobin', value: '11.6', range: '12–15.5', status: 'Low', previous_value: '13.1' },
    { test: 'LDL Cholesterol', value: '162', range: '<100', status: 'High' },
    { test: 'TSH', value: '2.1', range: '0.4–4.0', status: 'Normal' },
    { test: 'Creatinine', value: '0.9', range: '0.6–1.1', status: 'Normal' },
  ];

  it('assigns organ systems', () => {
    expect(organSystemOf(metrics[0]).key).toBe('hematology');
    expect(organSystemOf(metrics[1]).key).toBe('lipids');
    expect(organSystemOf(metrics[2]).key).toBe('thyroid');
    expect(organSystemOf(metrics[3]).key).toBe('renal');
  });

  it('summarizes triage counts and orders systems by severity', () => {
    const t = summarizeTriage(metrics);
    expect(t.total).toBe(4);
    expect(t.flagged).toBe(2);
    expect(t.drops).toBe(1);
    expect(t.systems[0].key).toBe('lipids');
  });

  it('sorts flagged rows first and filters', () => {
    const sorted = sortFlaggedFirst(metrics).map((m) => m.test);
    expect(sorted.slice(0, 2)).toEqual(['LDL Cholesterol', 'Hemoglobin']);
    expect(filterMetrics(metrics, 'flagged')).toHaveLength(2);
    expect(filterMetrics(metrics, 'drops').map((m) => m.test)).toEqual(['Hemoglobin']);
  });

  it('merges multiple reports and baseline previous_value into a time series', () => {
    const series = buildTrendSeries([
      { docId: 'b', date: '2026-10-24', metrics: [{ test: 'Hemoglobin', value: '13.1' }] },
      { docId: 'a', date: '2026-11-04', metrics: [{ test: 'Hemoglobin', value: '11.6', previous_value: '13.1', previous_date: '24 Oct 2026' }] },
    ]);
    const hb = series.get('hemoglobin');
    expect(hb.points.map((p) => p.value)).toEqual([13.1, 11.6]);
    expect(hb.change).toBe(-11.5);
  });

  it('keeps synthetic baseline point when previous_date is missing', () => {
    const series = buildTrendSeries([
      { docId: 'a', date: '2026-11-04', metrics: [{ test: 'Vitamin D', value: '30.0', previous_value: '22.0' }] },
    ]);
    const vitD = series.get('vitamind');
    expect(vitD.points.map((p) => p.value)).toEqual([22.0, 30.0]);
  });

  it('strips outer quotes only when both start and end are quotes', () => {
    expect(stripOuterQuotes('"Explain "HbA1c""')).toBe('Explain "HbA1c"');
    expect(stripOuterQuotes('Explain "HbA1c"')).toBe('Explain "HbA1c"');
    expect(stripOuterQuotes('"What does this mean?"')).toBe('What does this mean?');
    expect(stripOuterQuotes("'What does this mean?'")).toBe('What does this mean?');
    expect(stripOuterQuotes('“What does this mean?”')).toBe('What does this mean?');
  });
});

describe('EU decimal commas, comparators, and qualitative serology', () => {
  it('parses EU decimal commas and thousand separators', () => {
    expect(parseNumeric('6,8')).toBe(6.8);
    expect(parseNumeric('11,200')).toBe(11200);
  });

  it('parses ranges with EU decimal commas and trailing units', () => {
    expect(parseRange('3,9 - 5,6')).toEqual({ low: 3.9, high: 5.6, kind: 'between' });
    expect(parseRange('13.5 - 17.5 g/dL')).toEqual({ low: 13.5, high: 17.5, kind: 'between' });
  });

  it('classifies status with EU decimal values and ranges', () => {
    expect(classifyStatus({ status: 'Normal', value: '6,8', range: '3,9 - 5,6' })).toBe('high');
  });

  it('classifies status with comparator values exceeding bounds', () => {
    expect(classifyStatus({ status: 'Normal', value: '> 200', range: '10 - 200' })).toBe('high');
  });

  it('classifies qualitative serology with positive finding against negative range', () => {
    expect(classifyStatus({ status: 'Normal', value: 'Positive (1:160)', range: 'Negative' })).toBe('high');
    expect(classifyStatus({ status: 'Normal', value: 'Negative', range: 'Negative' })).toBe('normal');
    expect(classifyStatus({ status: '', value: 'Negative', range: 'Negative' })).toBe('normal');
    expect(classifyStatus({ status: '', value: '6.5', range: 'Adult: 4.0-10.0; Child: 5.0-13.0' })).toBe('unknown');
  });
});
