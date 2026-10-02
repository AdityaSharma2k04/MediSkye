// API Service for FastAPI backend
import { logger } from './logger';

const API_BASE = 'http://127.0.0.1:8000';

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

function getAuthHeaders() {
  const token = localStorage.getItem('token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
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

  const res = await fetch(`${API_BASE}/upload`, {
    method: 'POST',
    headers: {
      ...getAuthHeaders(),
    },
    body: formData,
  });

  const data = await res.json();
  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      throw new Error('Session expired. Please log in again.');
    }
    throw new Error(data.detail || 'Failed to extract text from PDF report.');
  }
  return data;
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

  const res = await fetch(`${API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(payload),
    ...(signal ? { signal } : {}),
  });

  if (!res.ok) {
    if (res.status === 401) {
      localStorage.removeItem('token');
      window.location.href = '/login';
      throw new Error('Session expired. Please log in again.');
    }

    let errorDetail = 'Server error while querying MediSkye.';
    try {
      const errorData = await res.json();
      errorDetail = errorData.detail || errorData.error || errorDetail;
    } catch (e) {}
    throw new Error(errorDetail);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() || ''; // Keep incomplete trailing line in buffer

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed.startsWith('data: ')) {
        const dataStr = trimmed.replace('data: ', '').trim();
        if (dataStr === '[DONE]') {
          return;
        }
        if (dataStr) {
          try {
            const dataObj = JSON.parse(dataStr);
            onChunk(dataObj);
          } catch (e) {
            logger.error('Failed to parse SSE data', e);
          }
        }
      }
    }
  }

  if (buffer.trim().startsWith('data: ')) {
    const dataStr = buffer.trim().replace('data: ', '').trim();
    if (dataStr && dataStr !== '[DONE]') {
      try {
        const dataObj = JSON.parse(dataStr);
        onChunk(dataObj);
      } catch (e) {}
    }
  }
}

export async function fetchLabMetrics(documentId) {
  try {
    const res = await fetch(`${API_BASE}/extract-metrics`, {
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
        window.location.href = '/login';
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

export async function getProfile() {
  const res = await fetch(`${API_BASE}/users/me`, {
    method: 'GET',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to fetch profile');
  }
  return await res.json();
}

export async function updateProfile(data) {
  const res = await fetch(`${API_BASE}/users/me`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    throw new Error('Failed to update profile');
  }
  return await res.json();
}

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
  const res = await fetch(`${API_BASE}/users/me/documents/${docId}/chats`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export async function renameChat(documentId, newTitle) {
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
    throw new Error(errData.detail || 'Failed to rename chat');
  }
  return await res.json();
}

// ── Patient Memory System APIs ──

export async function getMemoryStatus() {
  const res = await fetch(`${API_BASE}/users/me/memory/status`, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return { memory_consent_granted: false, fact_count: 0 };
  return await res.json();
}

export async function updateMemoryConsent(consent) {
  const res = await fetch(`${API_BASE}/users/me/memory/consent`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify({ consent }),
  });
  if (!res.ok) {
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
  const res = await fetch(url, {
    headers: getAuthHeaders(),
  });
  if (!res.ok) return [];
  return await res.json();
}

export const getMemoryFacts = getFacts;

export async function createFact(factData) {
  const res = await fetch(`${API_BASE}/users/me/facts`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(factData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to save health fact');
  }
  return await res.json();
}

export const createMemoryFact = createFact;

export async function updateFact(factId, factData) {
  const res = await fetch(`${API_BASE}/users/me/facts/${factId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeaders(),
    },
    body: JSON.stringify(factData),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to update health fact');
  }
  return await res.json();
}

export async function deleteFact(factId) {
  const res = await fetch(`${API_BASE}/users/me/facts/${factId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
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
  const res = await fetch(url, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    throw new Error('Failed to clear memory facts');
  }
  return await res.json();
}

// ── Multi-Document Chat APIs ──

export async function detachChatDocument(chatId, docId) {
  const res = await fetch(`${API_BASE}/chats/${chatId}/documents/${docId}`, {
    method: 'DELETE',
    headers: getAuthHeaders(),
  });
  if (!res.ok) {
    const errData = await res.json().catch(() => ({}));
    throw new Error(errData.detail || 'Failed to detach document from chat');
  }
  return await res.json();
}

