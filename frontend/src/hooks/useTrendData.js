import { useEffect, useMemo, useRef, useState } from 'react';
import { getMetricTrends, getCachedTrends } from '../services/api';
import { loadMetricsFor } from './useLabMetrics';
import { buildTrendSeries, parseClinicalDate, normalizeName, parseNumeric } from '../lib/clinical';

const MAX_REPORTS = 8;
const CONCURRENCY = 3;

async function mapLimit(items, limit, fn) {
  const out = new Array(items.length);
  let i = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (i < items.length) {
      const idx = i++;
      out[idx] = await fn(items[idx], idx);
    }
  });
  await Promise.all(workers);
  return out;
}

/** Convert the optional backend payload into the same Map shape buildTrendSeries returns. */
function seriesFromServer(payload) {
  const map = new Map();
  (payload.series || []).forEach((s) => {
    const key = s.key || normalizeName(s.name);
    const points = (s.points || [])
      .map((p, idx) => ({
        t: parseClinicalDate(p.collected_at) ?? idx,
        value: typeof p.value === 'number' ? (Number.isFinite(p.value) ? p.value : null) : parseNumeric(p.value),
        raw: p.raw_value ?? String(p.value),
        docId: p.document_id || null,
        label: p.collected_at || '',
        status: p.status || null,
        synthetic: false,
      }))
      .filter((p) => Number.isFinite(p.value))
      .sort((a, b) => a.t - b.t);
    const first = points[0];
    const last = points[points.length - 1];
    map.set(key, {
      key,
      name: s.name,
      unit: s.unit || '',
      range: s.reference_range || '',
      points,
      change: first && last && first !== last && first.value !== 0 ? Math.round(((last.value - first.value) / Math.abs(first.value)) * 1000) / 10 : null,
    });
  });
  return map;
}

/**
 * Longitudinal biomarker series for one patient.
 * 1. Try GET /users/me/metrics/trends (optional backend route).
 * 2. Fall back to fetching /extract-metrics for up to 8 recent reports and
 *    merging them client-side (cache-shared with useLabMetrics).
 *
 * @param {{patientId: string, reports: Array<{id,title,filename,collected_at,created_at}>, enabled: boolean}} args
 */
export default function useTrendData({ patientId, reports, enabled }) {
  const reportList = useMemo(() => {
    const list = Array.isArray(reports) ? reports.filter((r) => r && r.id) : [];
    return list
      .map((r) => ({ ...r, _t: parseClinicalDate(r.collected_at) ?? parseClinicalDate(r.created_at) ?? 0 }))
      .sort((a, b) => b._t - a._t)
      .slice(0, MAX_REPORTS);
  }, [reports]);

  const signature = `${patientId || 'self'}::${reportList.map((r) => r.id).join(',')}`;

  const [state, setState] = useState(() => {
    const cached = getCachedTrends(patientId);
    if (cached && Array.isArray(cached.series) && cached.series.length) {
      return {
        key: signature,
        series: seriesFromServer(cached),
        loading: false,
        source: 'cache',
        reportCount: (cached.reports || []).length,
      };
    }
    return { key: '', series: new Map(), loading: false, source: null, reportCount: 0 };
  });
  const reqRef = useRef(0);

  // Synchronously update on signature change for 0ms frame rendering
  const [prevSig, setPrevSig] = useState(signature);
  if (prevSig !== signature) {
    setPrevSig(signature);
    const cached = getCachedTrends(patientId);
    if (cached && Array.isArray(cached.series) && cached.series.length) {
      setState({
        key: signature,
        series: seriesFromServer(cached),
        loading: false,
        source: 'cache',
        reportCount: (cached.reports || []).length,
      });
    }
  }

  useEffect(() => {
    if (!enabled) return undefined;
    if (state.key === signature && !state.loading && state.series.size > 0) return undefined;

    const cached = getCachedTrends(patientId);
    const initialSeries =
      cached && Array.isArray(cached.series) && cached.series.length
        ? seriesFromServer(cached)
        : new Map();

    const hasCachedTrends = initialSeries.size > 0;

    setState((prev) => ({
      key: signature,
      series: prev.series.size > 0 ? prev.series : initialSeries,
      loading: prev.series.size === 0 && !hasCachedTrends,
      source: prev.series.size > 0 ? prev.source : (hasCachedTrends ? 'cache' : null),
      reportCount: (cached?.reports || []).length,
    }));

    // If cache already has trends, do NOT fire a duplicate fetch request to the backend! Render cached data immediately in 0ms!
    if (hasCachedTrends) {
      return undefined;
    }

    const reqId = ++reqRef.current;
    const controller = typeof AbortController !== 'undefined' ? new AbortController() : null;

    (async () => {
      let server = null;
      try {
        server = await getMetricTrends(patientId, { signal: controller?.signal });
      } catch {
        server = null;
      }
      if (reqId !== reqRef.current) return;
      if (server && server.series.length) {
        setState({ key: signature, series: seriesFromServer(server), loading: false, source: 'server', reportCount: (server.reports || []).length });
        return;
      }

      const snapshots = await mapLimit(reportList, CONCURRENCY, async (r) => {
        const metrics = await loadMetricsFor(r.id);
        return {
          docId: r.id,
          label: r.title || r.filename || 'Report',
          date: r.collected_at || metrics?.collected_at || r.created_at,
          metrics,
        };
      });
      if (reqId !== reqRef.current) return;
      const usable = snapshots.filter((s) => Array.isArray(s.metrics) && s.metrics.length);
      setState({ key: signature, series: buildTrendSeries(usable), loading: false, source: 'client', reportCount: usable.length });
    })();

    return () => controller?.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, signature]);

  return state;
}
