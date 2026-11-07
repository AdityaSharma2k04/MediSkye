import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchLabMetrics } from '../services/api';
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
 * Lab metrics for the active document.
 * @param {string|null} documentId
 * @param {{enabled?: boolean}} options  set enabled=false to defer the request
 */
export default function useLabMetrics(documentId, { enabled = true } = {}) {
  const [state, setState] = useState({ docId: null, metrics: [], loading: false, loaded: false, error: null });
  const reqRef = useRef(0);

  const load = useCallback(
    async (force = false) => {
      if (!documentId) {
        setState({ docId: null, metrics: [], loading: false, loaded: false, error: null });
        return [];
      }
      const reqId = ++reqRef.current;
      setState((s) => ({
        docId: documentId,
        metrics: s.docId === documentId ? s.metrics : [],
        loading: true,
        loaded: s.docId === documentId && s.loaded,
        error: null,
      }));
      try {
        const metrics = await loadMetricsFor(documentId, { force });
        if (reqId === reqRef.current) {
          const err = metrics?._error || null;
          setState({ docId: documentId, metrics, loading: false, loaded: true, error: err });
        }
        return metrics;
      } catch (err) {
        if (reqId === reqRef.current) {
          setState({ docId: documentId, metrics: [], loading: false, loaded: true, error: err?.message || 'Failed to load metrics' });
        }
        return [];
      }
    },
    [documentId]
  );

  useEffect(() => {
    if (!enabled || !documentId) return;
    if (state.docId === documentId && (state.loaded || state.loading)) return;
    load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, documentId]);

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
