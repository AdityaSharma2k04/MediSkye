// API Service for FastAPI backend
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
    console.error('Logout error:', err);
  } finally {
    localStorage.removeItem('token');
    localStorage.removeItem('mediskye_session_id');
    localStorage.removeItem('mediskye_conversations');
    localStorage.removeItem('mediskye_patient_id');
    localStorage.removeItem('mediskye_user_email');
  }
}

export async function uploadPdfReport(file, patientId = null) {
  const formData = new FormData();
  formData.append('file', file);
  if (patientId && patientId !== 'self') {
    formData.append('patient_id', patientId);
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

export async function sendQueryStream(queryText, documentId, language = 'English', onChunk, patientId = null) {
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

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    const chunkStr = decoder.decode(value, { stream: true });
    const lines = chunkStr.split('\n');

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const dataStr = line.replace('data: ', '').trim();
        if (dataStr === '[DONE]') {
          return;
        }
        if (dataStr) {
          try {
            const dataObj = JSON.parse(dataStr);
            onChunk(dataObj);
          } catch (e) {
            console.error('Failed to parse SSE data', e);
          }
        }
      }
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
    console.error('Failed to fetch metrics:', err);
    return [];
  }
}

export async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE}/docs`, { method: 'HEAD' });
    return res.ok;
  } catch (err) {
    return false;
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
