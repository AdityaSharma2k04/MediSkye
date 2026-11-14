// API Service for FastAPI backend
import { logger } from './logger';
import {
  auth,
  signOut,
  onAuthStateChanged,
  isSessionExpiredByInactivity,
  touchAuthActivity,
  FIFTEEN_DAYS_MS,
  getSavedAuthSession,
  saveAuthSession,
  performExplicitLogout,
} from './firebase';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

if (typeof window !== 'undefined' && auth && typeof onAuthStateChanged === 'function') {
  try {
    onAuthStateChanged(auth, async (user) => {
      if (user && user.emailVerified !== false) {
        try {
          const token = await user.getIdToken();
          localStorage.setItem('token', token);
          localStorage.setItem('mediskye_auth_id_token', token);
          touchAuthActivity();
          saveAuthSession(user, token);
        } catch (_) {}
      }
    });
  } catch (_) {}
}

export function formatApiError(data, fallback = 'Something went wrong on our end. Please try again.') {
  if (!data) return fallback;
  if (typeof data === 'string') return data;
  if (data.detail) {
    if (typeof data.detail === 'string') return data.detail;
    if (Array.isArray(data.detail)) {
      return data.detail
        .map(err => {
          const field = err.loc ? err.loc[err.loc.length - 1] : '';
          const msg = err.msg || 'Invalid value';
          return field && field !== 'body' ? `${field}: ${msg}` : msg;
        })
        .join('; ');
    }
    if (typeof data.detail === 'object') {
      return data.detail.msg || data.detail.message || JSON.stringify(data.detail);
    }
  }
  if (data.message && typeof data.message === 'string') return data.message;
  return fallback;
}

export function getStableCacheUid(explicitUid) {
  if (explicitUid) return explicitUid;
  if (typeof window === 'undefined') return 'default';
  try {
    if (auth && auth.currentUser && auth.currentUser.uid) {
      const uid = auth.currentUser.uid;
      try {
        localStorage.setItem('mediskye_last_uid', uid);
      } catch (_) {}
      return uid;
    }
    const rawSnap = localStorage.getItem('mediskye_auth_user_snapshot');
    if (rawSnap) {
      const snap = JSON.parse(rawSnap);
      if (snap?.uid) {
        try {
          localStorage.setItem('mediskye_last_uid', snap.uid);
        } catch (_) {}
        return snap.uid;
      }
    }
    const lastUid = localStorage.getItem('mediskye_last_uid');
    if (lastUid) return lastUid;

    const token = localStorage.getItem('token');
    if (token) {
      const parts = token.split('.');
      if (parts.length >= 2) {
        const payload = JSON.parse(atob(parts[1].replace(/-/g, '+').replace(/_/g, '/')));
        const tokenUid = payload.user_id || payload.sub || null;
        if (tokenUid) return tokenUid;
      }
    }
  } catch (_) {}
  return 'default';
}

export function getCurrentUid() {
  return getStableCacheUid();
}

export function warmBackendConnection() {
  if (typeof window === 'undefined') return;
  try {
    fetch(`${API_BASE}/health`, {
      method: 'GET',
      mode: 'cors',
      credentials: 'omit',
    }).catch(() => {});
  } catch (_) {}
}

export function safeStorageSet(key, value) {
  if (typeof window === 'undefined' || !key) return;
  const strVal = typeof value === 'string' ? value : JSON.stringify(value);
  try {
    localStorage.setItem(key, strVal);
  } catch (err) {
    // Quota exceeded: clean up old cached document summaries, metrics, and trends (LRU / temporary cache keys)
    try {
      const keysToClean = new Set();
      try {
        for (let i = 0; i < localStorage.length; i++) {
          const k = localStorage.key(i);
          if (k) keysToClean.add(k);
        }
      } catch (_) {}
      try {
        Object.keys(localStorage).forEach((k) => keysToClean.add(k));
      } catch (_) {}

      keysToClean.forEach((k) => {
        if (
          k &&
          (k.startsWith('mediskye_cached_doc_') ||
            k.startsWith('mediskye_cached_trends_') ||
            k.startsWith('mediskye_cached_msgs_') ||
            k.startsWith('mediskye_sample_'))
        ) {
          try {
            localStorage.removeItem(k);
          } catch (_) {}
        }
      });
      localStorage.setItem(key, strVal);
    } catch (_) {}
  }
}

export function safeStorageGet(key, fallback = null) {
  if (typeof window === 'undefined' || !key) return fallback;
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_) {
    return fallback;
  }
}

export function getCachedProfile(uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  return safeStorageGet(`mediskye_cached_profile_${stableUid}`, null);
}

export function setCachedProfile(profileOrUid, uidOrProfile) {
  let profile = profileOrUid;
  let uid = uidOrProfile;
  if (typeof profileOrUid === 'string' && typeof uidOrProfile === 'object') {
    uid = profileOrUid;
    profile = uidOrProfile;
  }
  const stableUid = getStableCacheUid(uid);
  if (!profile) return;
  safeStorageSet(`mediskye_cached_profile_${stableUid}`, profile);
}

export function getCachedDependents(uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  return safeStorageGet(`mediskye_cached_dependents_${stableUid}`, []);
}

export function setCachedDependents(dependentsOrUid, uidOrDependents) {
  let dependents = dependentsOrUid;
  let uid = uidOrDependents;
  if (typeof dependentsOrUid === 'string' && Array.isArray(uidOrDependents)) {
    uid = dependentsOrUid;
    dependents = uidOrDependents;
  }
  const stableUid = getStableCacheUid(uid);
  safeStorageSet(`mediskye_cached_dependents_${stableUid}`, dependents || []);
}

export function getCachedDocuments(patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  return safeStorageGet(`mediskye_cached_documents_${stableUid}_${patientId || 'self'}`, []);
}

export function setCachedDocuments(docs, patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  safeStorageSet(`mediskye_cached_documents_${stableUid}_${patientId || 'self'}`, docs || []);
}

// ── Per-Document Metrics & Summary ──

export function getCachedDocMetrics(docId) {
  if (!docId) return null;
  return safeStorageGet(`mediskye_cached_doc_metrics_${docId}`, null);
}

export function setCachedDocMetrics(docId, metrics) {
  if (!docId || !metrics) return;
  safeStorageSet(`mediskye_cached_doc_metrics_${docId}`, metrics);
}

export function getCachedDocSummary(docId) {
  if (!docId) return null;
  return safeStorageGet(`mediskye_cached_doc_summary_${docId}`, null);
}

export function setCachedDocSummary(docId, summary) {
  if (!docId || !summary) return;
  safeStorageSet(`mediskye_cached_doc_summary_${docId}`, summary);
}

// ── Memory Vault Facts Cache ──

export function getCachedMemoryFacts(patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  return safeStorageGet(`mediskye_cached_facts_${stableUid}_${patientId || 'self'}`, []);
}

export function setCachedMemoryFacts(facts, patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  safeStorageSet(`mediskye_cached_facts_${stableUid}_${patientId || 'self'}`, facts || []);
}

// ── Longitudinal Biomarker Trends Cache ──

export function getCachedTrends(patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  return safeStorageGet(`mediskye_cached_trends_${stableUid}_${patientId || 'self'}`, null);
}

export function setCachedTrends(trends, patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  if (!trends) return;
  safeStorageSet(`mediskye_cached_trends_${stableUid}_${patientId || 'self'}`, trends);
}

// ── Persistent Chat Sessions Cache ──

export function getCachedConversations(patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  return safeStorageGet(`mediskye_conversations_${stableUid}_${patientId || 'self'}`, null);
}

export function setCachedConversations(conversations, patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  if (!conversations) return;
  safeStorageSet(`mediskye_conversations_${stableUid}_${patientId || 'self'}`, conversations);
}

// ── Per-Chat Message History Cache ──

export function getCachedChatMessages(chatKey, uid = getStableCacheUid()) {
  if (!chatKey) return [];
  const stableUid = getStableCacheUid(uid);
  return safeStorageGet(`mediskye_cached_msgs_${stableUid}_${chatKey}`, []);
}

export function setCachedChatMessages(chatKey, messages, uid = getStableCacheUid()) {
  if (!chatKey || !messages) return;
  const stableUid = getStableCacheUid(uid);
  safeStorageSet(`mediskye_cached_msgs_${stableUid}_${chatKey}`, messages);
}

export function purgePatientLocalCache(patientId = 'self', uid = getStableCacheUid()) {
  const stableUid = getStableCacheUid(uid);
  try {
    const patKey = patientId || 'self';
    localStorage.removeItem(`mediskye_cached_documents_${stableUid}_${patKey}`);
    localStorage.removeItem(`mediskye_cached_facts_${stableUid}_${patKey}`);
    localStorage.removeItem(`mediskye_cached_trends_${stableUid}_${patKey}`);
    localStorage.removeItem(`mediskye_conversations_${stableUid}_${patKey}`);
  } catch (_) {}
}

export function purgeDocumentLocalCache(docId) {
  if (!docId) return;
  try {
    localStorage.removeItem(`mediskye_cached_doc_metrics_${docId}`);
    localStorage.removeItem(`mediskye_cached_doc_summary_${docId}`);
  } catch (_) {}
}

export function isJwtExpiredOrExpiringSoon(jwtString, bufferSeconds = 300) {
  if (!jwtString || typeof jwtString !== 'string') return true;
  const parts = jwtString.split('.');
  if (parts.length < 2) return true;
  try {
    const base64Url = parts[1];
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/');
    const payload = JSON.parse(atob(base64));
    if (!payload?.exp) return true;
    return (payload.exp * 1000) - Date.now() < bufferSeconds * 1000;
  } catch (_) {
    return true;
  }
}

export function isWithinFifteenDays() {
  return !isSessionExpiredByInactivity();
}

export async function getAuthToken(forceRefresh = false) {
  if (typeof window === 'undefined') return null;

  if (auth) {
    if (!auth.currentUser && typeof auth.authStateReady === 'function') {
      const snap = localStorage.getItem('mediskye_auth_user_snapshot');
      if (snap && isWithinFifteenDays()) {
        try {
          await auth.authStateReady();
        } catch (_) {}
      }
    }

    if (auth.currentUser) {
      const cachedToken = localStorage.getItem('mediskye_auth_id_token') || localStorage.getItem('token');
      if (forceRefresh || !cachedToken || isJwtExpiredOrExpiringSoon(cachedToken, 300)) {
        try {
          const freshToken = await auth.currentUser.getIdToken(true);
          if (freshToken) {
            localStorage.setItem('mediskye_auth_id_token', freshToken);
            localStorage.setItem('token', freshToken);
            touchAuthActivity();
            return freshToken;
          }
        } catch (err) {
          logger.warn('Failed to force refresh Firebase auth token:', err);
        }
      } else {
        try {
          const token = await auth.currentUser.getIdToken(false);
          if (token) {
            localStorage.setItem('mediskye_auth_id_token', token);
            localStorage.setItem('token', token);
            return token;
          }
        } catch (err) {
          logger.warn('Failed to get token without refresh:', err);
        }
      }
    }
  }

  // Fallback to raw cached token in localStorage (e.g., while offline)
  const fallback = localStorage.getItem('token') || localStorage.getItem('mediskye_auth_id_token');
  return fallback || null;
}

export function getAuthHeaders() {
  const token = localStorage.getItem('token') || localStorage.getItem('mediskye_auth_id_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

export async function getFreshAuthHeaders(forceRefresh = false) {
  const token = await getAuthToken(forceRefresh);
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

export async function apiFetch(url, options = {}, timeoutMs = 30000) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    throw new Error('You appear to be offline. Please check your internet connection and try again.');
  }

  const controller = new AbortController();
  let timedOut = false;
  const timeoutId = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);

  let combinedSignal = controller.signal;
  if (options.signal) {
    if (options.signal.aborted) {
      clearTimeout(timeoutId);
      throw new DOMException('The user aborted a request.', 'AbortError');
    }
    options.signal.addEventListener('abort', () => {
      controller.abort();
    });
  }

  const token = await getAuthToken(false);
  const baseHeaders = token ? { 'Authorization': `Bearer ${token}` } : getAuthHeaders();
  const headers = {
    ...baseHeaders,
    ...(options.headers || {}),
  };

  const isGet = !options.method || options.method.toUpperCase() === 'GET';
  const fetchOptions = {
    ...options,
    headers,
    signal: combinedSignal,
    ...(isGet && !options.cache ? { cache: 'no-store' } : {}),
  };

  let res;
  try {
    res = await fetch(url, fetchOptions);
  } catch (err) {
    clearTimeout(timeoutId);
    if (timedOut) {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s. Please check your connection and try again.`);
    }
    throw err;
  }

  // 401 Interceptor: retry once with fresh token if available
  if (res.status === 401 && auth) {
    try {
      if (!auth.currentUser && typeof auth.authStateReady === 'function') {
        const snap = localStorage.getItem('mediskye_auth_user_snapshot');
        if (snap && isWithinFifteenDays()) {
          await auth.authStateReady();
        }
      }
      if (auth.currentUser) {
        const freshToken = await getAuthToken(true);
        if (freshToken) {
          const retryHeaders = {
            ...headers,
            'Authorization': `Bearer ${freshToken}`,
          };
          res = await fetch(url, { ...fetchOptions, headers: retryHeaders });
        }
      }
    } catch (refreshErr) {
      logger.warn('Token auto-refresh failed on 401:', refreshErr);
    }
  }

  clearTimeout(timeoutId);

  // If still 401, throw HTTP error but NEVER wipe login session on API failure
  if (res.status === 401) {
    throw new Error('Unauthorized request (401). Please check permissions or try again.');
  }

  return res;
}

export async function login(email, password) {
  const normalizedEmail = (email || '').trim().toLowerCase();
  const formData = new URLSearchParams();
  formData.append('username', normalizedEmail);
  formData.append('password', password);

  const res = await fetch(`${API_BASE}/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: formData,
  });
  
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(formatApiError(data, 'Login failed'));
  }
  return data;
}

export async function register(email, password, phi_consent_granted) {
  const normalizedEmail = (email || '').trim().toLowerCase();
  const res = await fetch(`${API_BASE}/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ 
      email: normalizedEmail, 
      password, 
      phi_consent_granted: Boolean(phi_consent_granted) 
    }),
  });
  
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    throw new Error(formatApiError(data, 'Registration failed'));
  }
  return data;
}

/**
 * Remove every auth/PHI-bearing key this app writes to storage.
 *
 * Keys are namespaced under `mediskye_` (plus the raw `token`). Clearing the
 * whole namespace guarantees no cached patient data (conversations, patient
 * selection, last active user, consent flags) survives a logout on a shared
 * device. Non-MediSkye keys are left untouched.
 *
 * Pure UI preferences (theme, language) are NOT auth/PHI state, so they are
 * preserved across logout to avoid a theme/language flash on re-login.
 */
const PRESERVED_STORAGE_KEYS = new Set(['mediskye_theme', 'mediskye_language', 'mediskye_ui_lang', 'mediskye_explicit_logout']);

export function clearLocalAuthStorage() {
  try {
    const keysToRemove = [];
    for (let i = 0; i < localStorage.length; i += 1) {
      const key = localStorage.key(i);
      if (
        key &&
        (key === 'token' ||
          (key.startsWith('mediskye_') && !PRESERVED_STORAGE_KEYS.has(key)))
      ) {
        keysToRemove.push(key);
      }
    }
    keysToRemove.forEach((key) => localStorage.removeItem(key));
  } catch (err) {
    logger.error('Failed to clear localStorage:', err);
  }
  try {
    sessionStorage.removeItem('mediskye_consent_prompted');
  } catch (err) {
    logger.error('Failed to clear sessionStorage:', err);
  }
}

export async function logout() {
  const token = localStorage.getItem('token');
  try {
    if (token) {
      await fetch(`${API_BASE}/logout`, {
        method: 'POST',
        headers: getAuthHeaders(),
      });
    }
  } catch (err) {
    logger.error('Logout error:', err);
  } finally {
    try {
      await performExplicitLogout();
    } catch (e) {
      // ignore
    }
    clearLocalAuthStorage();
  }
}

export async function uploadPdfReport(file, patientId = null, chatId = null, customTitle = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (patientId && patientId !== 'self') {
    formData.append('patient_id', patientId);
  }
  if (chatId) {
    formData.append('chat_id', chatId);
  }
  if (customTitle) {
    formData.append('title', customTitle);
  }

  const res = await apiFetch(`${API_BASE}/upload`, {
    method: 'POST',
    body: formData,
  }, 60000);

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to extract text from PDF report.');
  }
  return data;
}

export async function getUploadStatus(jobId, timeoutMs = 10000) {
  const res = await apiFetch(`${API_BASE}/upload/status/${jobId}`, {}, timeoutMs);
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || 'Failed to fetch upload status');
  }
  return await res.json();
}

function sleepWithAbort(ms, signal) {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      const err = new Error('The operation was aborted.');
      err.name = 'AbortError';
      return reject(err);
    }
    let timer = null;
    const onAbort = () => {
      if (timer) clearTimeout(timer);
      const err = new Error('The operation was aborted.');
      err.name = 'AbortError';
      reject(err);
    };
    timer = setTimeout(() => {
      signal?.removeEventListener?.('abort', onAbort);
      resolve();
    }, ms);
    signal?.addEventListener?.('abort', onAbort, { once: true });
  });
}

export async function sendQueryStream(queryText, documentId, language = 'English', onChunk, patientId = null, signal = undefined, sessionId = null) {
  // documentId can be null for general-health queries (no PDF uploaded)
  const activeSessionId = sessionId || documentId || 'general-health-' + Date.now();
  const payload = {
    session_id: activeSessionId,
    query: queryText,
    language: language,
  };
  if (documentId && documentId !== activeSessionId) {
    payload.document_id = documentId;
  }
  if (patientId && patientId !== 'self') {
    payload.patient_id = patientId;
  }

  const RETRY_DELAYS = [800, 1500, 2500, 3500, 5000];
  const maxAttempts = 1 + RETRY_DELAYS.length;
  let lastError = null;

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (signal?.aborted) {
      const abortErr = new Error('The operation was aborted.');
      abortErr.name = 'AbortError';
      throw abortErr;
    }

    try {
      let res = await apiFetch(`${API_BASE}/query`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
        signal,
      }, 180000);

      if (!res.ok) {
        const isNonRetryable = (
          res.status === 400 ||
          res.status === 401 ||
          res.status === 403 ||
          res.status === 404 ||
          res.status === 409 ||
          res.status === 422
        );

        let errorDetail = res.status >= 500
          ? 'Something went wrong on our end. Please try again.'
          : 'Unable to complete your request. Please try again.';
        try {
          const errorData = await res.json();
          if (errorData && (errorData.detail || errorData.error)) {
            errorDetail = errorData.detail || errorData.error;
          }
        } catch (e) {}

        const err = new Error(errorDetail);
        err.status = res.status;

        if (isNonRetryable) {
          throw err;
        }

        lastError = err;
        if (attempt < RETRY_DELAYS.length) {
          const retryAfterSec = parseInt(res.headers?.get?.('Retry-After') || '', 10);
          const waitMs = (!isNaN(retryAfterSec) && retryAfterSec > 0)
            ? retryAfterSec * 1000
            : RETRY_DELAYS[attempt];
          logger.info(`Received ${res.status} from /query (attempt ${attempt + 1}/${maxAttempts}). Retrying after ${waitMs}ms...`);
          onChunk?.({
            stage: 'generating',
            message: `Retrying connection (${attempt + 1}/${RETRY_DELAYS.length})...`,
          });
          await sleepWithAbort(waitMs, signal);
          continue;
        }
        throw err;
      }

      const reader = res.body.getReader();
      await parseSSEStream(reader, onChunk);
      return;
    } catch (err) {
      if (err.name === 'AbortError' || signal?.aborted) {
        throw err;
      }
      if (err.status && (err.status === 400 || err.status === 401 || err.status === 403 || err.status === 404 || err.status === 409 || err.status === 422)) {
        throw err;
      }

      lastError = err;
      if (attempt < RETRY_DELAYS.length) {
        const waitMs = RETRY_DELAYS[attempt];
        logger.warn(`sendQueryStream failed on attempt ${attempt + 1}/${maxAttempts}: ${err.message}. Retrying in ${waitMs}ms...`);
        onChunk?.({
          replace: '',
          stage: 'generating',
          message: `Reconnecting stream (${attempt + 1}/${RETRY_DELAYS.length})...`,
        });
        await sleepWithAbort(waitMs, signal);
        continue;
      }
      throw err;
    }
  }

  if (lastError) {
    throw lastError;
  }
}

export async function parseSSEStream(reader, callbacks = {}) {
  const { onStage, onSpecialists, onContent, onChunk } = typeof callbacks === 'function'
    ? { onChunk: callbacks }
    : callbacks;

  const stageHandler = onStage || (onChunk ? (d) => onChunk(d) : undefined);
  const specHandler = onSpecialists || (onChunk ? (d) => onChunk(Array.isArray(d) ? { specialists: d } : (d?.specialists ? d : { specialists: d })) : undefined);
  const contentHandler = onContent || (onChunk ? (d) => onChunk(d) : undefined);

  const decoder = new TextDecoder('utf-8');
  let buffer = '';
  let currentEvent = 'message';
  let currentData = '';
  let sawDone = false;

  const dispatch = () => {
    if (!currentData) return;
    if (currentData === '[DONE]') {
      sawDone = true;
      return;
    }
    try {
      const parsed = JSON.parse(currentData);
      if (parsed && typeof parsed === 'object' && parsed.error) {
        sawDone = true;
      }
      if (currentEvent === 'stage') stageHandler?.(parsed);
      else if (currentEvent === 'specialists') specHandler?.(parsed);
      else contentHandler?.(parsed);
    } catch (e) {
      logger.warn('SSE parse error', e);
    }
  };

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || '';

    for (const rawLine of lines) {
      const line = rawLine.replace(/\r$/, '');
      if (line === '') {
        dispatch();
        currentEvent = 'message';
        currentData = '';
      } else if (line.startsWith('event:')) {
        currentEvent = line.slice(6).trim();
      } else if (line.startsWith('data:')) {
        currentData += line.slice(5).trim();
      }
    }
  }

  if (currentData) {
    dispatch();
  }

  if (!sawDone) {
    throw new Error('The response was interrupted. Please try again.');
  }
}

export async function fetchLabMetrics(documentId, forceRefresh = false) {
  try {
    const query = forceRefresh ? '?force_refresh=true' : '';
    const endpoint = `${API_BASE}/extract-metrics${query}`;
    const makeRequest = () =>
      apiFetch(endpoint, {
        method: 'POST',
        headers: {
          'X-Session-ID': documentId,
          ...getAuthHeaders(),
        },
      }, 60000);

    let res = await makeRequest();

    // Transparent retry for 503 Service Unavailable / 425 Too Early / 429 Too Many Requests with Retry-After honoring
    if (res.status === 503 || res.status === 425 || res.status === 429) {
      const retryAfter = parseInt(res.headers?.get?.('Retry-After') || '2', 10);
      const waitMs = Math.max(isNaN(retryAfter) ? 2 : retryAfter, 2) * 1000;
      logger.info(`Received ${res.status} from /extract-metrics. Transparent retry after ${waitMs}ms...`);
      await new Promise((resolve) => setTimeout(resolve, waitMs));
      res = await makeRequest();
    }

    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const list = [];
      list._error = data.detail || `Failed to fetch metrics (${res.status})`;
      return list;
    }
    const list = Array.isArray(data.metrics) ? data.metrics : [];
    list.collected_at = data.collected_at;
    list.is_future_collection_date = data.is_future_collection_date;
    list.prior_document_id = data.prior_document_id;
    list.prior_document_date = data.prior_document_date;
    if (documentId && list.length > 0) {
      setCachedDocMetrics(documentId, list);
    }
    return list;
  } catch (err) {
    logger.error('Failed to fetch metrics:', err);
    const cached = getCachedDocMetrics(documentId);
    if (Array.isArray(cached) && cached.length > 0) {
      return cached;
    }
    const list = [];
    list._error = err.message || 'Failed to fetch metrics';
    return list;
  }
}

export async function getDocumentSummary(documentId, forceRefresh = false) {
  const query = forceRefresh ? '?force_refresh=true' : '';
  let res = await apiFetch(`${API_BASE}/users/me/documents/${documentId}/summary${query}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  }, 60000);

  // Transparent retry for 503 / 425 / 429 with Retry-After honoring
  if (res.status === 503 || res.status === 425 || res.status === 429) {
    const retryAfter = parseInt(res.headers?.get?.('Retry-After') || '2', 10);
    const waitMs = Math.max(isNaN(retryAfter) ? 2 : retryAfter, 2) * 1000;
    logger.info(`Received ${res.status} from summary. Transparent retry after ${waitMs}ms...`);
    await new Promise((resolve) => setTimeout(resolve, waitMs));
    res = await apiFetch(`${API_BASE}/users/me/documents/${documentId}/summary${query}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    }, 60000);
  }

  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const cached = getCachedDocSummary(documentId);
    if (cached) return cached;
    throw new Error(data.detail || 'Failed to fetch document summary');
  }
  if (documentId && data) {
    setCachedDocSummary(documentId, data);
  }
  return data;
}

export async function getProfile() {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    const cached = getCachedProfile();
    if (cached) return cached;
  }
  try {
    const headers = await getFreshAuthHeaders();
    let res = await fetch(`${API_BASE}/users/me`, {
      method: 'GET',
      headers,
      cache: 'no-store',
    });
    if (res.status === 401 && auth && auth.currentUser) {
      try {
        const retryHeaders = await getFreshAuthHeaders(true);
        res = await fetch(`${API_BASE}/users/me`, {
          method: 'GET',
          headers: retryHeaders,
          cache: 'no-store',
        });
      } catch (e) {
        // ignore retry error
      }
    }
    if (!res.ok) {
      const cached = getCachedProfile();
      if (cached) return cached;
      throw new Error('Failed to fetch profile');
    }
    const prof = await res.json();
    setCachedProfile(prof);
    return prof;
  } catch (err) {
    const cached = getCachedProfile();
    if (cached) return cached;
    throw err;
  }
}

export async function updateProfile(data) {
  const headers = await getFreshAuthHeaders();
  let res = await fetch(`${API_BASE}/users/me`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(data),
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(`${API_BASE}/users/me`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          ...retryHeaders,
        },
        body: JSON.stringify(data),
      });
    } catch (e) {
      // ignore retry error
    }
  }
  if (!res.ok) {
    throw new Error('Failed to update profile');
  }
  const updated = await res.json();
  setCachedProfile(updated);
  return updated;
}

/**
 * @deprecated Password changes are now handled directly with Firebase Auth. Kept for backward compatibility.
 */
export async function changePassword(currentPassword, newPassword) {
  const res = await fetch(`${API_BASE}/users/me/password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  if (!res.ok) {
    let errorDetail = 'Failed to change password';
    try {
      const errData = await res.json();
      errorDetail = errData.detail || errorDetail;
    } catch (e) {}
    throw new Error(errorDetail);
  }
  return await res.json();
}

export async function deleteAccount() {
  const res = await fetch(`${API_BASE}/users/me`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to delete account');
  }
  clearLocalAuthStorage();
  if (auth && typeof signOut === 'function') {
    await signOut(auth);
  }
}

export async function getDependents() {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    const cached = getCachedDependents();
    return Array.isArray(cached) ? cached : [];
  }
  try {
    const res = await fetch(`${API_BASE}/users/me/dependents`, {
      method: 'GET',
      headers: getAuthHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) {
      const cached = getCachedDependents();
      if (Array.isArray(cached) && cached.length > 0) return cached;
      throw new Error('Failed to fetch dependents');
    }
    const deps = await res.json();
    if (Array.isArray(deps)) {
      setCachedDependents(deps);
    }
    return deps;
  } catch (err) {
    const cached = getCachedDependents();
    if (Array.isArray(cached) && cached.length > 0) return cached;
    return [];
  }
}

export async function createDependent(data) {
  const res = await fetch(`${API_BASE}/users/me/dependents`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to create dependent profile');
  }
  const created = await res.json();
  const currentCached = getCachedDependents();
  setCachedDependents([...currentCached.filter((d) => d.id !== created.id), created]);
  return created;
}

export async function updateDependent(id, data) {
  const res = await fetch(`${API_BASE}/users/me/dependents/${id}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to update dependent profile');
  }
  const updated = await res.json();
  const currentCached = getCachedDependents();
  setCachedDependents(currentCached.map((d) => (d.id === id ? updated : d)));
  return updated;
}

export async function deleteDependent(id) {
  const res = await fetch(`${API_BASE}/users/me/dependents/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to delete dependent profile');
  }
  const currentCached = getCachedDependents();
  setCachedDependents(currentCached.filter((d) => d.id !== id));
  purgePatientLocalCache(id);
}

export async function getUserDocuments(patientId = 'self') {
  const patKey = patientId || 'self';
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    const cached = getCachedDocuments(patKey);
    return Array.isArray(cached) ? cached : [];
  }
  try {
    let url = `${API_BASE}/users/me/documents`;
    if (patientId && patientId !== 'self') {
      url += `?patient_id=${encodeURIComponent(patientId)}`;
    }
    const res = await fetch(url, {
      headers: getAuthHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) {
      const cached = getCachedDocuments(patKey);
      return Array.isArray(cached) ? cached : [];
    }
    const docs = await res.json();
    if (Array.isArray(docs)) {
      setCachedDocuments(docs, patKey);
    }
    return docs;
  } catch (err) {
    const cached = getCachedDocuments(patKey);
    return Array.isArray(cached) ? cached : [];
  }
}

export const getDocuments = getUserDocuments;

export async function getDocumentChats(docId, sessionId = null) {
  const chatKey = docId ? `doc_${docId}` : (sessionId ? `session_${sessionId}` : null);
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return chatKey ? getCachedChatMessages(chatKey) : [];
  }
  try {
    let url = docId ? `${API_BASE}/users/me/documents/${docId}/chats` : `${API_BASE}/users/me/chats`;
    if (!docId && sessionId) {
      url += `?session_id=${encodeURIComponent(sessionId)}`;
    }
    const res = await fetch(url, {
      headers: getAuthHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) {
      return chatKey ? getCachedChatMessages(chatKey) : [];
    }
    const messages = await res.json();
    if (Array.isArray(messages) && chatKey) {
      setCachedChatMessages(chatKey, messages);
    }
    return Array.isArray(messages) ? messages : [];
  } catch (_) {
    return chatKey ? getCachedChatMessages(chatKey) : [];
  }
}

export async function getGeneralChats(sessionId = null) {
  const chatKey = sessionId ? `session_${sessionId}` : 'general_all';
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return getCachedChatMessages(chatKey);
  }
  try {
    let url = `${API_BASE}/users/me/chats`;
    if (sessionId) {
      url += `?session_id=${encodeURIComponent(sessionId)}`;
    }
    const res = await fetch(url, {
      headers: getAuthHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) {
      return getCachedChatMessages(chatKey);
    }
    const messages = await res.json();
    if (Array.isArray(messages)) {
      setCachedChatMessages(chatKey, messages);
    }
    return Array.isArray(messages) ? messages : [];
  } catch (_) {
    return getCachedChatMessages(chatKey);
  }
}

export async function getChatSessions(patientId = 'self') {
  if (typeof navigator !== 'undefined' && !navigator.onLine) {
    return [];
  }
  try {
    let url = `${API_BASE}/users/me/chats/sessions`;
    if (patientId && patientId !== 'self') {
      url += `?patient_id=${encodeURIComponent(patientId)}`;
    }
    const res = await fetch(url, {
      headers: getAuthHeaders(),
      cache: 'no-store',
    });
    if (!res.ok) return [];
    const sessions = await res.json();
    return Array.isArray(sessions) ? sessions : [];
  } catch (_) {
    return [];
  }
}

export async function renameChatSession(sessionId, title) {
  let res = await fetch(`${API_BASE}/users/me/chats/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ title }),
  });
  if (res.status === 404) {
    return await renameDocument(sessionId, title);
  }
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    logger.warn('Failed to rename chat session on server:', {
      status: res.status,
      body: errData,
      sessionId,
    });
    throw new Error(errData.detail || 'Failed to rename chat session');
  }
  return await res.json();
}

export async function deleteChatSession(sessionId, patientId = 'self') {
  // Purge from cached conversations for patient
  try {
    const cached = getCachedConversations(patientId);
    if (Array.isArray(cached)) {
      setCachedConversations(
        cached.filter((c) => c.id !== sessionId && c.sessionId !== sessionId),
        patientId
      );
    }
  } catch (_) {}

  let res = await fetch(`${API_BASE}/users/me/chats/sessions/${encodeURIComponent(sessionId)}`, {
    method: 'DELETE',
    headers: { ...getAuthHeaders() },
  });
  if (res.status === 404) {
    return await deleteDocument(sessionId);
  }
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to delete chat session');
  }
  return true;
}

export async function clearAllChats(patientId = null, clearPatientContext = true) {
  let url = `${API_BASE}/users/me/chats?clear_patient_context=${clearPatientContext ? 'true' : 'false'}`;
  if (patientId && patientId !== 'all') {
    url += `&patient_id=${encodeURIComponent(patientId)}`;
    setCachedConversations([], patientId);
  } else if (patientId === 'all') {
    setCachedConversations([], 'self');
  }
  const res = await fetch(url, {
    method: 'DELETE',
    headers: { ...getAuthHeaders() },
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to clear chat sessions');
  }
  return true;
}

export const clearAllChatSessions = clearAllChats;

export async function renameDocument(documentId, newTitle) {
  let res = await fetch(`${API_BASE}/users/me/documents/${documentId}/title`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ title: newTitle }),
  });
  if (!res.ok && res.status === 404) {
    res = await fetch(`${API_BASE}/documents/${documentId}/title`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ title: newTitle }),
    });
  }
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    logger.warn('Failed to rename document on server:', {
      status: res.status,
      body: errData,
      documentId,
    });
    throw new Error(errData.detail || 'Failed to rename chat');
  }
  return await res.json();
}

export async function reassignDocumentPatient(documentId, patientId) {
  const res = await apiFetch(`${API_BASE}/users/me/documents/${documentId}/patient`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ patient_id: patientId || 'self' }),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    logger.warn('Failed to reassign document patient on server:', {
      status: res.status,
      body: errData,
      documentId,
      patientId,
    });
    throw new Error(errData.detail || 'Failed to reassign document to patient profile');
  }
  return await res.json();
}

export const renameChat = renameChatSession;

export async function deleteDocument(documentId, patientId = 'self') {
  try {
    const patKey = patientId || 'self';
    const cachedDocs = getCachedDocuments(patKey);
    if (Array.isArray(cachedDocs)) {
      setCachedDocuments(cachedDocs.filter((d) => d.id !== documentId), patKey);
    }
    const cachedConvs = getCachedConversations(patKey);
    if (Array.isArray(cachedConvs)) {
      setCachedConversations(
        cachedConvs.filter((c) => c.id !== documentId && c.document_id !== documentId),
        patKey
      );
    }
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem(`mediskye_cached_doc_metrics_${documentId}`);
    }
  } catch (_) {}

  const res = await fetch(`${API_BASE}/users/me/documents/${documentId}`, {
    method: 'DELETE',
    headers: { ...getAuthHeaders() },
  });
  if (res.status === 404) {
    // Already deleted or not a server document
    return true;
  }
  if (!res.ok) throw new Error('Failed to delete document');
  return true;
}

export const deleteChat = deleteChatSession;

// ── Patient Memory System APIs ──

export async function getMemoryStatus() {
  const headers = await getFreshAuthHeaders();
  let res = await fetch(`${API_BASE}/users/me/memory/status`, {
    headers,
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(`${API_BASE}/users/me/memory/status`, {
        headers: retryHeaders,
      });
    } catch (e) {
      // ignore
    }
  }
  if (!res.ok) return { memory_consent_granted: false, fact_count: 0 };
  return await res.json();
}

export async function updateMemoryConsent(consent) {
  const headers = await getFreshAuthHeaders();
  let res = await fetch(`${API_BASE}/users/me/memory/consent`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify({ consent }),
  });

  // If 401 Unauthorized, force-refresh the Firebase ID token and retry
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(`${API_BASE}/users/me/memory/consent`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...retryHeaders,
        },
        body: JSON.stringify({ consent }),
      });
    } catch (retryErr) {
      logger.warn('Retry with refreshed token failed:', retryErr);
    }
  }

  // Graceful fallback to updateProfile if /users/me/memory/consent fails
  if (!res.ok) {
    try {
      const updatedProfile = await updateProfile({ memory_consent_granted: consent });
      if (updatedProfile) {
        return {
          status: 'success',
          memory_consent_granted: updatedProfile.memory_consent_granted ?? consent,
        };
      }
    } catch (fallbackErr) {
      // Re-raise original error if fallback also fails
    }
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to update memory consent');
  }
  return await res.json();
}

export async function getFacts(patientId = null) {
  const patKey = patientId || 'self';
  let url = `${API_BASE}/users/me/facts`;
  if (patientId && patientId !== 'self') {
    url += `?patient_id=${encodeURIComponent(patientId)}`;
  }
  const headers = await getFreshAuthHeaders();
  let res = await fetch(url, {
    headers,
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(url, {
        headers: retryHeaders,
      });
    } catch (e) {
      // ignore
    }
  }
  if (!res.ok) {
    const cached = getCachedMemoryFacts(patKey);
    return Array.isArray(cached) ? cached : [];
  }
  const data = await res.json();
  const list = Array.isArray(data) ? data : [];
  setCachedMemoryFacts(list, patKey);
  return list;
}

export const getMemoryFacts = getFacts;

export async function createFact(factData, patientId = null) {
  let url = `${API_BASE}/users/me/facts`;
  const resolvedPatientId = patientId || factData.patient_id || factData.dependent_id;
  const patKey = resolvedPatientId || 'self';
  if (resolvedPatientId && resolvedPatientId !== 'self') {
    url += `?patient_id=${encodeURIComponent(resolvedPatientId)}`;
  }
  const payload = {
    ...factData,
    ...(resolvedPatientId && resolvedPatientId !== 'self'
      ? { patient_id: resolvedPatientId, dependent_id: resolvedPatientId }
      : {}),
  };
  const headers = await getFreshAuthHeaders();
  let res = await fetch(url, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(payload),
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...retryHeaders,
        },
        body: JSON.stringify(payload),
      });
    } catch (e) {
      // ignore
    }
  }
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to save health fact');
  }
  const created = await res.json();
  if (created && created.id) {
    const current = getCachedMemoryFacts(patKey);
    setCachedMemoryFacts([created, ...current.filter((f) => f.id !== created.id)], patKey);
  }
  return created;
}

export const createMemoryFact = createFact;

export async function updateFact(factId, factData, patientId = null) {
  const patKey = patientId || 'self';
  let url = `${API_BASE}/users/me/facts/${factId}`;
  if (patientId && patientId !== 'self') {
    url += `?patient_id=${encodeURIComponent(patientId)}`;
  }
  const headers = await getFreshAuthHeaders();
  let res = await fetch(url, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(factData),
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(url, {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          ...retryHeaders,
        },
        body: JSON.stringify(factData),
      });
    } catch (e) {
      // ignore
    }
  }
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to update health fact');
  }
  const updated = await res.json();
  if (updated && updated.id) {
    const current = getCachedMemoryFacts(patKey);
    setCachedMemoryFacts(current.map((f) => (f.id === updated.id ? updated : f)), patKey);
  }
  return updated;
}

export async function deleteFact(factId, patientId = null) {
  const patKey = patientId || 'self';
  // Immediate write-through cache purge
  const current = getCachedMemoryFacts(patKey);
  setCachedMemoryFacts(current.filter((f) => f.id !== factId), patKey);

  let url = `${API_BASE}/users/me/facts/${factId}`;
  if (patientId && patientId !== 'self') {
    url += `?patient_id=${encodeURIComponent(patientId)}`;
  }
  const headers = await getFreshAuthHeaders();
  let res = await fetch(url, {
    method: 'DELETE',
    headers,
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(url, {
        method: 'DELETE',
        headers: retryHeaders,
      });
    } catch (e) {
      // ignore
    }
  }
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to delete health fact');
  }
  return await res.json();
}

export const deleteMemoryFact = deleteFact;

export async function clearAllMemoryFacts(patientId = null) {
  const patKey = patientId || 'self';
  setCachedMemoryFacts([], patKey);
  let url = `${API_BASE}/users/me/memory/facts`;
  if (patientId && patientId !== 'self') {
    url += `?patient_id=${encodeURIComponent(patientId)}`;
  }
  const headers = await getFreshAuthHeaders();
  let res = await fetch(url, {
    method: 'DELETE',
    headers,
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(url, {
        method: 'DELETE',
        headers: retryHeaders,
      });
    } catch (e) {
      // ignore
    }
  }
  if (!res.ok) {
    throw new Error('Failed to clear memory facts');
  }
  return await res.json();
}

// ── Multi-Document Chat APIs ──

export async function detachChatDocument(chatId, docId) {
  const documentId = docId || chatId;
  return await deleteDocument(documentId);
}

// ── Chat History Export ──

export async function exportDocumentData(documentId) {
  const headers = await getFreshAuthHeaders();
  const res = await fetch(`${API_BASE}/users/me/documents/${documentId}/export`, {
    method: 'GET',
    headers: { ...headers },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || 'Failed to export document data');
  }
  return await res.json();
}

export async function exportUserAccountData() {
  const headers = await getFreshAuthHeaders();
  const res = await fetch(`${API_BASE}/users/me/export-data`, {
    method: 'GET',
    headers: { ...headers },
  });
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || 'Failed to export account data');
  }
  return await res.json();
}

// ── Custom Verification & Generic API Client ──

export const api = {
  post: async (endpoint, data = {}, options = {}) => {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    const res = await apiFetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(options.headers || {}),
      },
      body: JSON.stringify(data),
      ...options,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      throw new Error(formatApiError(errData, 'Request failed'));
    }
    return await res.json();
  },
  get: async (endpoint, options = {}) => {
    const url = endpoint.startsWith('http') ? endpoint : `${API_BASE}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    const res = await apiFetch(url, {
      method: 'GET',
      ...options,
    });
    if (!res.ok) {
      const errData = await res.json().catch(() => null);
      throw new Error(formatApiError(errData, 'Request failed'));
    }
    return await res.json();
  },
};

export async function sendCustomVerification(email) {
  return await api.post('/auth/send-custom-verification', { email });
}

export async function sendCustomPasswordReset(email) {
  return await api.post('/auth/send-custom-password-reset', { email });
}

export default api;

// ── Longitudinal Trends (optional backend enhancement) ──

/**
 * GET /users/me/metrics/trends — pre-aggregated per-biomarker time series.
 *
 * This endpoint is OPTIONAL. The frontend falls back to computing trends
 * client-side from per-document POST /extract-metrics results whenever this
 * returns null (404 / 405 / network error / unexpected payload).
 * See REDESIGN_CHANGELOG.md §3 for the exact response contract.
 */
export async function getMetricTrends(patientId = null, options = {}) {
  const patKey = patientId || 'self';
  let url = `${API_BASE}/users/me/metrics/trends`;
  if (patientId && patientId !== 'self') {
    url += `?patient_id=${encodeURIComponent(patientId)}`;
  }
  try {
    const res = await fetch(url, {
      headers: getAuthHeaders(),
      signal: options.signal,
    });
    if (!res.ok) {
      return getCachedTrends(patKey);
    }
    const data = await res.json().catch(() => null);
    if (!data || !Array.isArray(data.series)) {
      return getCachedTrends(patKey);
    }
    setCachedTrends(data, patKey);
    return data;
  } catch (err) {
    if (err?.name !== 'AbortError') {
      logger.info('Trends endpoint unavailable; using client-side computation or cached trends.');
    }
    return getCachedTrends(patKey);
  }
}

/**
 * Background Pre-Downloader
 * Pre-warms Memory Vault facts, longitudinal trends, and top document metrics
 * for the given patient without blocking the UI thread.
 */
export async function prewarmPatientLocalCache(patientId = 'self', dependents = [], documents = []) {
  if (typeof window === 'undefined') return;
  const targetPatient = patientId || 'self';

  // 1. Pre-warm Memory Vault facts for active profile if not already cached
  try {
    const cachedFacts = getCachedMemoryFacts(targetPatient);
    if (!cachedFacts || cachedFacts.length === 0) {
      await getFacts(targetPatient);
    }
  } catch (_) {}

  // 2. Pre-warm longitudinal trends if not already cached
  try {
    const cachedTrends = getCachedTrends(targetPatient);
    if (!cachedTrends) {
      await getMetricTrends(targetPatient);
    }
  } catch (_) {}

  // 3. Pre-warm up to top 5 documents' lab metrics without blocking
  try {
    const docs =
      Array.isArray(documents) && documents.length > 0
        ? documents
        : getCachedDocuments(targetPatient);
    const toPrewarm = (docs || []).slice(0, 5);
    for (const doc of toPrewarm) {
      const docId = doc.id || doc.document_id;
      if (docId && !getCachedDocMetrics(docId)) {
        await fetchLabMetrics(docId).catch(() => {});
      }
    }
  } catch (_) {}
}
