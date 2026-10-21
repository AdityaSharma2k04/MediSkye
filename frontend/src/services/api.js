// API Service for FastAPI backend
import { logger } from './logger';
import { auth, signOut } from './firebase';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export function formatApiError(data, fallback = 'Request failed') {
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

export function getAuthHeaders() {
  const token = localStorage.getItem('token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
}

export async function getFreshAuthHeaders(forceRefresh = false) {
  let token = localStorage.getItem('token');
  if (auth && auth.currentUser) {
    try {
      const freshToken = await auth.currentUser.getIdToken(forceRefresh);
      if (freshToken) {
        token = freshToken;
        localStorage.setItem('token', freshToken);
      }
    } catch (e) {
      logger.warn('Failed to refresh Firebase auth token:', e);
    }
  }
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

  const baseHeaders = getAuthHeaders();
  const headers = {
    ...baseHeaders,
    ...(options.headers || {}),
  };

  const fetchOptions = {
    ...options,
    headers,
    signal: combinedSignal,
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

  // 401 Interceptor: retry with fresh token if available
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const freshToken = await auth.currentUser.getIdToken(true);
      if (freshToken) {
        localStorage.setItem('token', freshToken);
        const retryHeaders = {
          ...headers,
          'Authorization': `Bearer ${freshToken}`,
        };
        res = await fetch(url, { ...fetchOptions, headers: retryHeaders });
      }
    } catch (refreshErr) {
      logger.warn('Token auto-refresh failed:', refreshErr);
    }
  }

  clearTimeout(timeoutId);

  if (res.status === 401) {
    localStorage.removeItem('token');
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new Event('auth:expired'));
    }
    throw new Error('Session expired. Please log in again.');
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
const PRESERVED_STORAGE_KEYS = new Set(['mediskye_theme', 'mediskye_language']);

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
      if (auth && typeof signOut === 'function') {
        await signOut(auth);
      }
    } catch (e) {
      // ignore
    }
    clearLocalAuthStorage();
  }
}

export async function uploadPdfReport(file, patientId = null, chatId = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (patientId && patientId !== 'self') {
    formData.append('patient_id', patientId);
  }
  if (chatId) {
    formData.append('chat_id', chatId);
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

export async function sendQueryStream(queryText, documentId, language = 'English', onChunk, patientId = null, signal = undefined) {
  // documentId can be null for general-health queries (no PDF uploaded)
  const payload = {
    session_id: documentId || 'general-health-' + Date.now(), // dummy UUID-like string; backend checks document existence
    query: queryText,
    language: language,
  };
  if (patientId && patientId !== 'self') {
    payload.patient_id = patientId;
  }

  const res = await apiFetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
    signal,
  }, 45000);

  if (!res.ok) {
    let errorDetail = 'Server error while querying MediSkye.';
    try {
      const errorData = await res.json();
      errorDetail = errorData.detail || errorData.error || errorDetail;
    } catch (e) {}
    throw new Error(errorDetail);
  }

  const reader = res.body.getReader();
  await parseSSEStream(reader, onChunk);
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

  const dispatch = () => {
    if (!currentData) return;
    if (currentData === '[DONE]') return;
    try {
      const parsed = JSON.parse(currentData);
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
}

export async function fetchLabMetrics(documentId, forceRefresh = false) {
  try {
    const query = forceRefresh ? '?force_refresh=true' : '';
    const res = await fetch(`${API_BASE}/extract-metrics${query}`, {
      method: 'POST',
      headers: {
        'X-Session-ID': documentId,
        ...getAuthHeaders(),
      },
    });
    const data = await res.json();
    if (!res.ok) {
      if (res.status === 401) {
        localStorage.removeItem('token');
        window.dispatchEvent(new Event('auth:expired'));
        throw new Error('Session expired. Please log in again.');
      }
      return [];
    }
    return data.metrics || [];
  } catch (err) {
    logger.error('Failed to fetch metrics:', err);
    return [];
  }
}

export async function getDocumentSummary(documentId, forceRefresh = false) {
  const query = forceRefresh ? '?force_refresh=true' : '';
  const res = await apiFetch(`${API_BASE}/users/me/documents/${documentId}/summary${query}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
  }, 60000);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || 'Failed to fetch document summary');
  }
  return data;
}

export async function getProfile() {
  const headers = await getFreshAuthHeaders();
  let res = await fetch(`${API_BASE}/users/me`, {
    method: 'GET',
    headers,
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(`${API_BASE}/users/me`, {
        method: 'GET',
        headers: retryHeaders,
      });
    } catch (e) {
      // ignore retry error
    }
  }
  if (!res.ok) {
    throw new Error('Failed to fetch profile');
  }
  return await res.json();
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
  return await res.json();
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
  localStorage.removeItem('token');
}

export async function getDependents() {
  const res = await fetch(`${API_BASE}/users/me/dependents`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to fetch dependents');
  }
  return await res.json();
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
  return await res.json();
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
  return await res.json();
}

export async function deleteDependent(id) {
  const res = await fetch(`${API_BASE}/users/me/dependents/${id}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to delete dependent profile');
  }
}

export async function getUserDocuments() {
  const res = await fetch(`${API_BASE}/users/me/documents`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export async function getDocumentChats(docId) {
  const url = docId ? `${API_BASE}/users/me/documents/${docId}/chats` : `${API_BASE}/users/me/chats`;
  const res = await fetch(url, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export async function getGeneralChats() {
  const res = await fetch(`${API_BASE}/users/me/chats`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export async function renameDocument(documentId, newTitle) {
  const res = await fetch(`${API_BASE}/documents/${documentId}/title`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ title: newTitle }),
  });
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

export const renameChat = renameDocument;

export async function deleteDocument(documentId) {
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

export const deleteChat = deleteDocument;

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

export async function getFacts(dependentId = null) {
  let url = `${API_BASE}/users/me/facts`;
  if (dependentId && dependentId !== 'self') {
    url += `?dependent_id=${dependentId}`;
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
  if (!res.ok) return [];
  return await res.json();
}

export const getMemoryFacts = getFacts;

export async function createFact(factData) {
  const headers = await getFreshAuthHeaders();
  let res = await fetch(`${API_BASE}/users/me/facts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    body: JSON.stringify(factData),
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(`${API_BASE}/users/me/facts`, {
        method: 'POST',
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
    throw new Error(errData.detail || 'Failed to save health fact');
  }
  return await res.json();
}

export const createMemoryFact = createFact;

export async function updateFact(factId, factData) {
  const headers = await getFreshAuthHeaders();
  let res = await fetch(`${API_BASE}/users/me/facts/${factId}`, {
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
      res = await fetch(`${API_BASE}/users/me/facts/${factId}`, {
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
  return await res.json();
}

export async function deleteFact(factId) {
  const headers = await getFreshAuthHeaders();
  let res = await fetch(`${API_BASE}/users/me/facts/${factId}`, {
    method: 'DELETE',
    headers,
  });
  if (res.status === 401 && auth && auth.currentUser) {
    try {
      const retryHeaders = await getFreshAuthHeaders(true);
      res = await fetch(`${API_BASE}/users/me/facts/${factId}`, {
        method: 'DELETE',
        headers: retryHeaders,
      });
    } catch (e) {
      // ignore
    }
  }
  if (!res.ok) {
    throw new Error('Failed to delete memory fact');
  }
  return await res.json();
}

export const deleteMemoryFact = deleteFact;

export async function clearAllMemoryFacts(dependentId = null) {
  let url = `${API_BASE}/users/me/memory/facts`;
  if (dependentId && dependentId !== 'self') {
    url += `?dependent_id=${dependentId}`;
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
  const res = await fetch(`${API_BASE}/users/me/documents/${documentId}/export`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('token');
      window.dispatchEvent(new Event('auth:expired'));
      throw new Error('Session expired. Please log in again.');
    }
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || 'Failed to export document data');
  }
  return await res.json();
}
