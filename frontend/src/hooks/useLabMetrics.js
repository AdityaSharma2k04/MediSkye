import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchLabMetrics, getCachedDocMetrics } from '../services/api';
import { logger } from '../services/logger';

/**
 * Module-level cache so the inspector, trend builder, command palette and
 * print flow share a single POST /extract-metrics per document per session.
 * Values are Promises (in-flight de-duplication) resolving to the metrics array
 * (with `collected_at`, `prior_document_id` … attached as array props).
 */
const cache = new Map();

export function invalidateMetrics(docId) {
  if (docId) cache.delete(docId);
  else cache.clear();
}

export async function loadMetricsFor(docId, { force = false } = {}) {
  if (!docId) return [];
  if (!force && cache.has(docId)) return cache.get(docId);
  const p = (async () => {
    try {
      const result = await fetchLabMetrics(docId, force);
      return Array.isArray(result) ? result : [];
    } catch (err) {
      logger.warn('Lab metrics unavailable:', err);
      cache.delete(docId);
      const cached = getCachedDocMetrics(docId);
      if (Array.isArray(cached) && cached.length > 0) {
        return cached;
      }
      const errList = [];
      errList._error = err.message || 'Lab metrics unavailable';
      return errList;
    }
  })();
  cache.set(docId, p);
  const value = await p;
  // Don't pin empty results or errors: the backend may still be warming the cache.
  if (!value.length || value._error) cache.delete(docId);
  return value;
}

/**
 * Fallback parser for extracting biomarkers strictly from Turn 1 report walkthrough.
 */
export function extractBiomarkersFromMessage(text) {
  if (!text || typeof text !== 'string') return [];
  try {
    const jsonMatch = text.match(/```(?:json)?\s*(\{[\s\S]*?\})\s*```/i);
    if (jsonMatch) {
      const parsed = JSON.parse(jsonMatch[1]);
      if (Array.isArray(parsed.metrics) && parsed.metrics.length > 0) {
        return parsed.metrics;
      }
      if (Array.isArray(parsed.lab_metrics) && parsed.lab_metrics.length > 0) {
        return parsed.lab_metrics;
      }
    }
  } catch (_) {}

  const lines = text.split('\n');
  const rows = [];
  let inTable = false;
  let headers = [];
  for (const line of lines) {
    const trimmed = line.trim();
    if (trimmed.startsWith('|') && trimmed.endsWith('|')) {
      const cells = trimmed.slice(1, -1).split('|').map((c) => c.trim());
      if (!inTable) {
        if (cells.some((c) => /test|biomarker|parameter|analyte|metric|investigation/i.test(c))) {
          headers = cells.map((c) => c.toLowerCase());
          inTable = true;
          continue;
        }
      } else {
        if (cells.every((c) => /^:?-+:?$/.test(c))) continue;
        const testIdx = headers.findIndex((h) => /test|biomarker|parameter|analyte|metric|investigation/i.test(h));
        const valIdx = headers.findIndex((h) => /value|result|observed/i.test(h));
        const unitIdx = headers.findIndex((h) => /unit/i.test(h));
        const rangeIdx = headers.findIndex((h) => /range|reference|biological/i.test(h));
        const statusIdx = headers.findIndex((h) => /status|flag/i.test(h));

        const name = testIdx >= 0 ? cells[testIdx] : cells[0];
        const value = valIdx >= 0 ? cells[valIdx] : (cells[1] || '');
        if (name && value && !/^[-—\s]+$/.test(name)) {
          rows.push({
            name,
            value,
            unit: unitIdx >= 0 ? cells[unitIdx] : '',
            range: rangeIdx >= 0 ? cells[rangeIdx] : '',
            status: statusIdx >= 0 ? cells[statusIdx].toLowerCase() : 'normal',
          });
        }
      }
    } else if (inTable && rows.length > 0) {
      inTable = false;
    }
  }
  return rows;
}

/**
 * Lab metrics for the active document.
 * @param {string|null} documentId
 * @param {{enabled?: boolean, messages?: Array}} options  set enabled=false to defer the request
 */
export default function useLabMetrics(documentId, { enabled = true, messages = [] } = {}) {
  const [state, setState] = useState(() => {
    const cached = documentId ? getCachedDocMetrics(documentId) : null;
    return {
      docId: documentId,
      metrics: Array.isArray(cached) ? cached : [],
      loading: !cached && Boolean(enabled && documentId),
      loaded: Boolean(cached && cached.length > 0),
      error: null,
    };
  });
  const reqRef = useRef(0);

  const load = useCallback(
    async (force = false) => {
      if (!documentId) {
        setState({ docId: null, metrics: [], loading: false, loaded: false, error: null });
        return [];
      }
      const reqId = ++reqRef.current;
      setState((s) => {
        const cached = s.docId === documentId ? s.metrics : (getCachedDocMetrics(documentId) || []);
        const hasData = Boolean(cached && cached.length > 0);
        return {
          docId: documentId,
          metrics: cached,
          loading: !hasData || force,
          loaded: hasData,
          error: null,
        };
      });
      try {
        const metrics = await loadMetricsFor(documentId, { force });
        if (reqId === reqRef.current) {
          const err = metrics?._error || null;
          setState({ docId: documentId, metrics, loading: false, loaded: true, error: err });
        }
        return metrics;
      } catch (err) {
        if (reqId === reqRef.current) {
          const cached = getCachedDocMetrics(documentId) || [];
          setState({
            docId: documentId,
            metrics: cached,
            loading: false,
            loaded: true,
            error: cached.length > 0 ? null : (err?.message || 'Failed to load metrics'),
          });
        }
        return [];
      }
    },
    [documentId]
  );

  useEffect(() => {
    if (!enabled || !documentId) return;
    if (state.docId === documentId && state.loaded) return;
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, documentId]);

  // Fallback metric extraction: ONLY if metrics are not loaded/cached yet,
  // and strictly from the first assistant message (Turn 1).
  useEffect(() => {
    if (!documentId) return;
    if (state.docId === documentId && Array.isArray(state.metrics) && state.metrics.length > 0) {
      // Canonical metrics already loaded, NEVER overwrite, filter or reduce!
      return;
    }
    if (!Array.isArray(messages) || messages.length === 0) return;

    // Find the first assistant message (Turn 1 report walkthrough)
    const firstAssistantMsg = messages.find(
      (m) => m && (m.sender === 'assistant' || m.role === 'assistant' || m.role === 'ai')
    );
    if (!firstAssistantMsg) return;

    const text = firstAssistantMsg.text || firstAssistantMsg.message || '';
    const extracted = extractBiomarkersFromMessage(text);
    if (extracted.length > 0) {
      setState((prev) => {
        if (prev.docId === documentId && Array.isArray(prev.metrics) && prev.metrics.length > 0) {
          return prev;
        }
        return {
          ...prev,
          docId: documentId,
          metrics: extracted,
          loaded: true,
          loading: false,
        };
      });
    }
  }, [documentId, messages, state.docId, state.metrics]);

  useEffect(() => {
    if (!documentId) {
      reqRef.current += 1;
      setState({ docId: null, metrics: [], loading: false, loaded: false, error: null });
    }
  }, [documentId]);

  const isCurrent = state.docId === documentId;
  return {
    metrics: isCurrent ? state.metrics : [],
    loading: isCurrent ? state.loading : Boolean(enabled && documentId),
    loaded: isCurrent && state.loaded,
    error: isCurrent ? state.error : null,
    reload: () => load(true),
    ensure: () => (isCurrent && state.loaded ? Promise.resolve(state.metrics) : load(false)),
  };
}
