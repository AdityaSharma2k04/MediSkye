import React, { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from './Sidebar';
import ChatWindow from './ChatWindow';
import ChatInput from './ChatInput';
import DocumentModal from './DocumentModal';
import SettingsModal from './SettingsModal';
import Profile from './Profile';
import Toast from './Toast';
import MemoryConsentModal from './MemoryConsentModal';
import {
  uploadPdfReport,
  getUploadStatus,
  sendQueryStream,
  logout,
  getProfile,
  getDependents,
  getUserDocuments,
  getDocumentChats,
  renameDocument,
  deleteAccount,
  updateProfile,
  detachChatDocument,
} from '../services/api';
import { useNavigate } from 'react-router-dom';
import { logger } from '../services/logger';

// ── Theme helpers ──────────────────────────────────────────
function getSystemTheme() {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

function getStoredThemePreference() {
  try {
    const stored = localStorage.getItem('mediskye_theme');
    if (stored === 'dark' || stored === 'light' || stored === 'system') return stored;
  } catch {}
  return 'system';
}

function resolveDarkMode(preference) {
  if (preference === 'system') return getSystemTheme() === 'dark';
  return preference === 'dark';
}

function applyThemeToDOM(theme) {
  if (theme === 'dark') {
    document.documentElement.classList.add('dark');
  } else {
    document.documentElement.classList.remove('dark');
  }
}

// ── Auto-naming heuristics ─────────────────────────────────
function cleanFilename(filename) {
  // Strip extension
  let name = filename.replace(/\.pdf$/i, '');
  // Replace _ and - with spaces
  name = name.replace(/[_-]+/g, ' ');
  // Remove common noise words (case-insensitive)
  name = name.replace(/\b(report|final|v\d+|rev|draft|scan|result|results|lab|blood|test|copy|sample|patient)\b/gi, '');
  // Remove pure-digit segments
  name = name.replace(/\b\d{4,}\b/g, '');
  // Collapse spaces
  name = name.replace(/\s{2,}/g, ' ').trim();
  // Title-case
  name = name.replace(/\w\S*/g, (w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase());
  // Limit to 40 chars, truncate at word boundary
  if (name.length > 40) {
    name = name.slice(0, 40).replace(/\s+\S*$/, '');
  }
  return name || 'New Conversation';
}

function autoNameFromQuery(query) {
  let name = query.trim();
  if (name.length <= 40) return name;
  const truncated = name.slice(0, 40).replace(/\s+\S*$/, '');
  return truncated + '...';
}

function generateSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
  });
}

export default function ChatApp() {
  const navigate = useNavigate();
  const userLoadedRef = useRef(null);

  const handleLogout = async () => {
    // Clear the JWT blocklist server-side, then wipe all local auth/PHI state.
    await logout();
    userLoadedRef.current = null;
    // Reset in-memory global state so a re-mount (or a deferred navigation)
    // cannot render stale patient data from the previous session.
    setCurrentUser(null);
    setDependents([]);
    setSelectedPatientId('self');
    const freshId = generateSessionId();
    setSessionId(freshId);
    setConversations([{ id: freshId, title: 'New Conversation', messages: [], pdf: null }]);
    setActivePdf(null);
    setIsSettingsOpen(false);
    setIsProfileOpen(false);
    navigate('/login', { replace: true });
  };

  const [sessionId, setSessionId] = useState(() => {
    const saved = localStorage.getItem('mediskye_session_id');
    if (saved && saved !== 'null' && saved !== 'undefined') return saved;
    const fresh = generateSessionId();
    try {
      localStorage.setItem('mediskye_session_id', fresh);
    } catch (e) {}
    return fresh;
  });

  // ── Patient Context & User State ──
  const [currentUser, setCurrentUser] = useState(null);
  const [dependents, setDependents] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(() => {
    return localStorage.getItem('mediskye_patient_id') || 'self';
  });
  const [profileInitialTab, setProfileInitialTab] = useState('profile');

  // ── Theme state: 'light' | 'dark' | 'system' — the raw preference is persisted ──
  const [themePreference, setThemePreference] = useState(() => getStoredThemePreference());
  const [darkMode, setDarkMode] = useState(() => resolveDarkMode(getStoredThemePreference()));
  const [language, setLanguage] = useState('English');

  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      return false;
    }
    return localStorage.getItem('mediskye_sidebar_open') !== 'false';
  });

  const toggleSidebar = () => {
    const next = !sidebarOpen;
    setSidebarOpen(next);
    localStorage.setItem('mediskye_sidebar_open', String(next));
  };
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState(null);

  const [activePdf, setActivePdf] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const abortControllerRef = useRef(null);
  const chatInputRef = useRef(null);
  const [toasts, setToasts] = useState([]);

  // Load User & Dependents on Mount
  const refreshPatientContext = useCallback(async () => {
    try {
      const [userRes, depsRes] = await Promise.all([
        getProfile().catch(() => null),
        getDependents().catch(() => []),
      ]);

      if (userRes) {
        setCurrentUser(userRes);
        if (userRes.language_preference) {
          setLanguage(userRes.language_preference);
        }
      }
      if (depsRes) {
        setDependents(depsRes);
      }
    } catch (e) {
      logger.error('Failed to load patient context:', e);
    }
  }, []);

  useEffect(() => {
    refreshPatientContext();
  }, [refreshPatientContext]);

  // Restore conversations from localStorage with account isolation
  const [conversations, setConversations] = useState(() => {
    try {
      const saved = localStorage.getItem('mediskye_conversations');
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const sanitized = parsed.map((c) => ({
            ...c,
            id: c.id && c.id !== 'null' ? c.id : generateSessionId(),
          }));
          return sanitized;
        }
      }
    } catch (e) {
      logger.error('Failed to load conversations from localStorage:', e);
    }
    const currentId = localStorage.getItem('mediskye_session_id') || generateSessionId();
    return [
      { id: currentId, title: 'New Conversation', messages: [], pdf: null },
    ];
  });

  // Keep conversations synchronized in localStorage
  useEffect(() => {
    try {
      localStorage.setItem('mediskye_conversations', JSON.stringify(conversations));
      if (currentUser?.id && userLoadedRef.current === currentUser.id) {
        localStorage.setItem(`mediskye_conversations_${currentUser.id}`, JSON.stringify(conversations));
      }
    } catch (e) {
      logger.error('Failed to save conversations to localStorage:', e);
    }
  }, [conversations, currentUser]);

  // Reusable document refresher: synchronizes server document truth with local state
  const refreshDocuments = useCallback(async (activeDocId = null) => {
    try {
      const docs = await getUserDocuments();
      if (!Array.isArray(docs)) return [];

      if (docs.length === 0) return [];

      const targetDocId = activeDocId || docs[0]?.id;
      let targetDocChats = [];
      if (targetDocId) {
        targetDocChats = await getDocumentChats(targetDocId).catch(() => []);
      }

      setConversations((prev) => {
        const existingMap = new Map();
        prev.forEach((c) => {
          if (c.id) existingMap.set(c.id, c);
          if (c.document_id) existingMap.set(c.document_id, c);
        });

        const syncedDocConvs = docs.map((doc) => {
          const existing = existingMap.get(doc.id);
          const pdfMeta = {
            id: doc.id,
            name: doc.filename,
            filename: doc.filename,
            size: 8192,
          };
          const autoTitle = doc.title || cleanFilename(doc.filename);

          let messages = existing?.messages || [];
          if (doc.id === targetDocId && targetDocChats.length > 0 && messages.length === 0) {
            messages = targetDocChats.map((c) => ({
              id: c.id,
              sender: c.role === 'ai' ? 'assistant' : 'user',
              text: c.message,
              timestamp: c.created_at ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
            }));
          }

          if (existing) {
            return {
              ...existing,
              id: doc.id,
              document_id: doc.id,
              patient_id: doc.dependent_id || existing.patient_id || 'self',
              title: existing.title && existing.title !== 'New Conversation' && existing.title !== 'New chat'
                ? existing.title
                : autoTitle,
              messages,
              pdf: existing.pdf || pdfMeta,
              documents: Array.isArray(existing.documents) && existing.documents.length > 0
                ? existing.documents
                : [pdfMeta],
              created_at: existing.created_at || doc.created_at,
            };
          }

          return {
            id: doc.id,
            document_id: doc.id,
            patient_id: doc.dependent_id || 'self',
            title: autoTitle,
            messages,
            pdf: pdfMeta,
            documents: [pdfMeta],
            created_at: doc.created_at,
          };
        });

        // Retain any conversation that does not correspond to a server document (e.g. empty new conversation)
        const nonDocConvs = prev.filter(
          (c) => !c.document_id && !docs.some((d) => d.id === c.id)
        );

        return [...syncedDocConvs, ...nonDocConvs];
      });

      if (targetDocId) {
        const targetDoc = docs.find((d) => d.id === targetDocId) || docs[0];
        const pdfMeta = {
          id: targetDoc.id,
          name: targetDoc.filename,
          filename: targetDoc.filename,
          size: 8192,
        };
        setActivePdf(pdfMeta);
        setSessionId(targetDoc.id);
        localStorage.setItem('mediskye_session_id', targetDoc.id);
      }
      return docs;
    } catch (err) {
      logger.error('Failed to refresh documents:', err);
      return [];
    }
  }, []);

  // Account switch isolation & pre-linked document loading
  useEffect(() => {
    if (currentUser?.id) {
      const isSwitch = userLoadedRef.current !== null && userLoadedRef.current !== currentUser.id;
      userLoadedRef.current = currentUser.id;
      const lastUser = localStorage.getItem('mediskye_last_active_user');
      const isStorageSwitch = lastUser && lastUser !== currentUser.id;
      const userSaved = localStorage.getItem(`mediskye_conversations_${currentUser.id}`);

      if (isSwitch || isStorageSwitch || !userSaved) {
        if (userSaved && !isSwitch && !isStorageSwitch) {
          try {
            const parsed = JSON.parse(userSaved);
            if (Array.isArray(parsed) && parsed.length > 0) {
              const sanitized = parsed.map((c) => ({
                ...c,
                id: c.id && c.id !== 'null' ? c.id : generateSessionId(),
              }));
              setConversations(sanitized);
              setSessionId(sanitized[0].id);
              setActivePdf(sanitized[0].pdf || null);
              return;
            }
          } catch (e) {}
        }

        // Fresh account or switched account without valid saved chats: check backend
        refreshDocuments().then((docs) => {
          if (!docs || docs.length === 0) {
            const freshId = generateSessionId();
            setSessionId(freshId);
            setActivePdf(null);
            setConversations([{ id: freshId, title: 'New Conversation', messages: [], pdf: null }]);
          }
        }).catch(() => {
          const freshId = generateSessionId();
          setSessionId(freshId);
          setActivePdf(null);
          setConversations([{ id: freshId, title: 'New Conversation', messages: [], pdf: null }]);
        });
      }
      localStorage.setItem('mediskye_last_active_user', currentUser.id);
    }
  }, [currentUser, refreshDocuments]);

  // ── Apply theme to DOM and persist the raw preference (incl. 'system') ──
  useEffect(() => {
    const isDark = resolveDarkMode(themePreference);
    setDarkMode(isDark);
    applyThemeToDOM(isDark ? 'dark' : 'light');
    try {
      localStorage.setItem('mediskye_theme', themePreference);
    } catch (e) {
      logger.error('Failed to persist theme preference:', e);
    }
  }, [themePreference]);

  // ── Follow OS theme changes only while the preference is 'system' ──
  useEffect(() => {
    const mq = window.matchMedia('(prefers-color-scheme: dark)');
    const handler = (e) => {
      if (themePreference === 'system') {
        setDarkMode(e.matches);
        applyThemeToDOM(e.matches ? 'dark' : 'light');
      }
    };
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, [themePreference]);

  // Memory consent prompt on first chat
  const [showMemoryConsentModal, setShowMemoryConsentModal] = useState(false);

  useEffect(() => {
    if (currentUser && currentUser.memory_consent_granted === false) {
      const alreadyPrompted = sessionStorage.getItem('mediskye_consent_prompted');
      if (!alreadyPrompted) {
        setShowMemoryConsentModal(true);
      }
    }
  }, [currentUser]);

  const handleAllowMemory = async () => {
    try {
      const updated = await updateProfile({ memory_consent_granted: true });
      setCurrentUser(updated);
      setShowMemoryConsentModal(false);
      showToast('success', 'Memory Enabled', 'MediSkye will remember key health context across sessions.');
    } catch (err) {
      showToast('error', 'Update Failed', err.message);
    }
  };

  const handleSkipMemory = () => {
    sessionStorage.setItem('mediskye_consent_prompted', 'true');
    setShowMemoryConsentModal(false);
  };

  // Restore active PDF state if present in current chat
  useEffect(() => {
    const current = conversations.find((c) => c.id === sessionId);
    if (current && Array.isArray(current.documents) && current.documents.length > 0) {
      setActivePdf(current.documents[0]);
    } else if (current && current.pdf) {
      setActivePdf(current.pdf);
    } else if (current && !current.pdf) {
      setActivePdf(null);
    }
  }, [sessionId, conversations]);

  const currentChat = conversations.find((c) => c.id === sessionId) || {
    id: sessionId,
    title: 'New Conversation',
    messages: [],
    documents: [],
  };

  const messages = currentChat.messages || [];

  const showToast = (type, title, message) => {
    const id = Date.now();
    setToasts((prev) => [...prev, { id, type, title, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4500);
  };

  const dismissToast = (id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  };

  const handlePatientSelect = (patientId) => {
    setSelectedPatientId(patientId);
    localStorage.setItem('mediskye_patient_id', patientId);
    const dep = dependents.find(d => d.id === patientId);
    if (dep) {
      showToast('info', 'Patient Context Switched', `Clinical lens updated to ${dep.full_name} (${dep.relationship}).`);
    } else {
      showToast('info', 'Patient Context Switched', `Clinical lens updated to ${currentUser?.full_name || 'Your profile'}.`);
    }
  };

  const handleOpenDependents = () => {
    setProfileInitialTab('dependents');
    setIsProfileOpen(true);
  };

  const handleOpenProfile = () => {
    setProfileInitialTab('profile');
    setIsProfileOpen(true);
  };

  const handleAttachFile = async (file) => {
    if (!file) return;

    const isValidType =
      file.type === 'application/pdf' ||
      file.name.match(/\.(pdf|jpg|jpeg|png)$/i);
    if (!isValidType) {
      showToast('error', 'Invalid File Format', 'Please upload a PDF, JPG, or PNG file.');
      return;
    }

    const maxMb = 50;
    if (file.size > maxMb * 1024 * 1024) {
      showToast('error', 'File Too Large', `Maximum allowed file size is ${maxMb}MB.`);
      return;
    }

    showToast('info', 'Uploading Report', 'Extracting text and creating vector embeddings...');
    setIsGenerating(true);

    try {
      const data = await uploadPdfReport(file, selectedPatientId, sessionId);

      let newDocId = null;
      if (data?.job_id) {
        const jobId = data.job_id;
        const startTime = Date.now();
        const POLL_INTERVAL = (typeof window !== 'undefined' && window.__POLL_INTERVAL__) || 2000;
        const MAX_WAIT = (typeof window !== 'undefined' && window.__UPLOAD_MAX_WAIT__) || 120000;
        let consecutiveFailures = 0;
        const MAX_CONSECUTIVE_FAILURES = 5;

        while (Date.now() - startTime < MAX_WAIT) {
          await new Promise((r) => setTimeout(r, POLL_INTERVAL));
          let status;
          try {
            status = await getUploadStatus(jobId, 10000);
            consecutiveFailures = 0;
          } catch (err) {
            consecutiveFailures += 1;
            logger.warn(`Upload status poll failed (${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES}):`, err);

            if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
              await refreshDocuments();
              showToast(
                'error',
                'Upload Status Lost',
                'Could not confirm upload status. The document may still be processing — refresh in 30 seconds.'
              );
              return;
            }
            continue;
          }

          if (status.status === 'completed') {
            newDocId = status.document_id;
            break;
          }

          if (status.status === 'failed') {
            throw new Error(status.error || 'Upload processing failed');
          }

          setUploadProgress(`Processing... (${Math.floor((Date.now() - startTime) / 1000)}s)`);
        }

        if (!newDocId) {
          await refreshDocuments();
          showToast(
            'info',
            'Upload Taking Longer Than Expected',
            'The document may still be processing. The document list was refreshed; check again in 30 seconds if it is not there yet.'
          );
          return;
        }
      } else if (data?.document_id) {
        newDocId = data.document_id;
      } else {
        throw new Error('Upload failed: no job_id or document_id received');
      }

      const pdfMeta = { id: newDocId, name: file.name, filename: file.name, size: file.size };
      setActivePdf(pdfMeta);
      showToast('success', 'Report Ready', 'Your report has been processed.');

      const autoTitle = cleanFilename(file.name);

      // Promote the conversation's id to the server's document_id so the
      // sidebar entry is stable across sessions (re-login fetches by doc.id).
      const prevSessionId = sessionId;
      setSessionId(newDocId);
      localStorage.setItem('mediskye_session_id', newDocId);

      // 1. Optimistically update local conversation state immediately
      setConversations((prev) => {
        const existingIdx = prev.findIndex((c) => c.id === prevSessionId || c.id === newDocId);
        if (existingIdx >= 0) {
          const current = prev[existingIdx];
          const currentDocs = Array.isArray(current.documents)
            ? current.documents
            : (current.pdf ? [{ id: current.document_id || 'doc-1', name: current.pdf.name, filename: current.pdf.name }] : []);
          const updatedDocs = [...currentDocs.filter((d) => d.id !== newDocId), pdfMeta];
          const updatedChat = {
            ...current,
            id: newDocId,
            document_id: newDocId,
            patient_id: selectedPatientId,
            title: (current.title === 'New Conversation' || current.title === 'New chat') ? autoTitle : current.title,
            pdf: pdfMeta,
            documents: updatedDocs,
          };
          const next = [...prev];
          next[existingIdx] = updatedChat;
          return next;
        } else {
          return [
            {
              id: newDocId,
              document_id: newDocId,
              patient_id: selectedPatientId,
              title: autoTitle,
              messages: [],
              pdf: pdfMeta,
              documents: [pdfMeta],
            },
            ...prev,
          ];
        }
      });

      // 2. Refetch document list from server to synchronize state with server truth
      await refreshDocuments(newDocId);
    } catch (err) {
      showToast('error', 'Upload Failed', err.message);
    } finally {
      setUploadProgress(null);
      setIsGenerating(false);
    }
  };

  const handleDetachDocument = async (docId) => {
    try {
      await detachChatDocument(sessionId, docId).catch(() => {});
      const current = conversations.find((c) => c.id === sessionId);
      const remainingDocs = (current?.documents || []).filter((d) => d.id !== docId);
      const nextActivePdf = remainingDocs.length > 0 ? remainingDocs[0] : null;
      // Side effects must live OUTSIDE the state updater (which may run twice).
      setActivePdf(nextActivePdf);
      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId
            ? {
                ...c,
                documents: remainingDocs,
                pdf: nextActivePdf,
                document_id: nextActivePdf ? nextActivePdf.id : null,
              }
            : c
        )
      );
      showToast('info', 'Report Detached', 'Document detached from this consultation.');
    } catch (err) {
      showToast('error', 'Detach Failed', err.message);
    }
  };

  const handleRemoveFile = () => {
    // Remove all documents from current conversation — downgrade to general session
    setActivePdf(null);
    setConversations((prev) =>
      prev.map((c) =>
        c.id === sessionId
          ? { ...c, pdf: null, document_id: null, documents: [] }
          : c
      )
    );
  };

  const handleSendMessage = async (userQuery, options = {}) => {
    if (!userQuery || isGenerating) return;
    const { appendUserMessage = true } = options;

    if (appendUserMessage) {
      const userMsgObj = {
        id: Date.now(),
        sender: 'user',
        text: userQuery,
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      // Auto-name from first message if title is still generic
      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId
            ? {
                ...c,
                title: (c.title === 'New Conversation' || c.title === 'New chat')
                  ? autoNameFromQuery(userQuery)
                  : c.title,
                messages: [...c.messages, userMsgObj],
              }
            : c
        )
      );
    }

    setIsGenerating(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    try {
      // Read document ID from current conversation
      let chatDocId = null;
      let chatPatientId = selectedPatientId;
      const chatObj = conversations.find(c => c.id === sessionId);
      chatDocId = chatObj?.document_id || null;
      if (chatObj?.patient_id) chatPatientId = chatObj.patient_id;

      const assistantMsgObj = {
        id: Date.now() + 1,
        sender: 'assistant',
        text: '',
        status: 'Analyzing your question...',
        isStreaming: true,
        sources: [],
        timestamp: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
      };

      setConversations((prev) =>
        prev.map((c) =>
          c.id === sessionId
            ? { ...c, messages: [...c.messages, assistantMsgObj] }
            : c
        )
      );

      // Send query — route through sessionId so backend searches ALL attached docs
      await sendQueryStream(userQuery, chatDocId || sessionId, language, (chunk) => {
        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== sessionId) return c;
            const newMsgs = [...c.messages];
            const lastMsg = { ...newMsgs[newMsgs.length - 1] };

            if (chunk.stage && chunk.message) {
              lastMsg.status = chunk.message;
            } else if (chunk.metrics) {
              lastMsg.metrics = chunk.metrics;
            } else if (chunk.sources) {
              lastMsg.sources = chunk.sources;
            } else if (chunk.specialists) {
              lastMsg.specialists = chunk.specialists;
            } else if (chunk.chunk || chunk.token) {
              lastMsg.text = (lastMsg.text || '') + (chunk.chunk || chunk.token);
              lastMsg.status = null;
            } else if (chunk.error) {
              lastMsg.error = chunk.error || 'Something went wrong. Tap to retry.';
              lastMsg.status = null;
              lastMsg.isStreaming = false;
            }

            newMsgs[newMsgs.length - 1] = lastMsg;
            return { ...c, messages: newMsgs };
          })
        );
      }, chatPatientId, controller.signal);

    } catch (err) {
      if (err && err.name === 'AbortError') {
        // User stopped generation — keep any partial text, skip the error toast.
      } else {
        showToast('error', 'Query Error', err.message);
        setConversations((prev) =>
          prev.map((c) => {
            if (c.id !== sessionId) return c;
            const newMsgs = [...c.messages];
            if (newMsgs.length > 0 && newMsgs[newMsgs.length - 1].sender === 'assistant') {
              const lastMsg = { ...newMsgs[newMsgs.length - 1] };
              lastMsg.error = err.message;
              lastMsg.status = null;
              lastMsg.isStreaming = false;
              newMsgs[newMsgs.length - 1] = lastMsg;
            }
            return { ...c, messages: newMsgs };
          })
        );
      }
    } finally {
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== sessionId) return c;
          const newMsgs = [...c.messages];
          if (newMsgs.length > 0 && newMsgs[newMsgs.length - 1].sender === 'assistant') {
            const lastMsg = { ...newMsgs[newMsgs.length - 1] };
            lastMsg.isStreaming = false;
            lastMsg.status = null;
            newMsgs[newMsgs.length - 1] = lastMsg;
          }
          return { ...c, messages: newMsgs };
        })
      );
      setIsGenerating(false);
      abortControllerRef.current = null;
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setIsGenerating(false);
  };

  const handleRegenerate = () => {
    if (isGenerating) return;
    const lastUserMsg = [...messages].reverse().find((m) => m.sender === 'user');
    if (!lastUserMsg) return;

    // Drop ONLY the trailing assistant message; the user's question is preserved.
    setConversations((prev) =>
      prev.map((c) => {
        if (c.id !== sessionId) return c;
        const msgs = [...c.messages];
        if (msgs.length > 0 && msgs[msgs.length - 1].sender === 'assistant') {
          msgs.pop();
        }
        return { ...c, messages: msgs };
      })
    );

    // Re-stream the same question WITHOUT appending a duplicate user bubble.
    handleSendMessage(lastUserMsg.text, { appendUserMessage: false });
  };

  const handleNewChat = () => {
    const newId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
    setSessionId(newId);
    localStorage.setItem('mediskye_session_id', newId);
    setActivePdf(null);
    setIsProfileOpen(false);
    setConversations((prev) => [
      { id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId },
      ...prev,
    ]);
    showToast('info', 'New Conversation Started');
  };

  const handleSelectChat = async (id) => {
    setSessionId(id);
    localStorage.setItem('mediskye_session_id', id);
    const chat = conversations.find((c) => c.id === id);
    if (chat) {
      setActivePdf(chat.pdf || null);
      if (chat.patient_id) {
        setSelectedPatientId(chat.patient_id);
      }
      if (chat.document_id && (!chat.messages || chat.messages.length === 0)) {
        try {
          const chats = await getDocumentChats(chat.document_id);
          if (Array.isArray(chats) && chats.length > 0) {
            const formatted = chats.map((c) => ({
              id: c.id,
              sender: c.role === 'ai' ? 'assistant' : 'user',
              text: c.message,
              timestamp: c.created_at ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '',
            }));
            setConversations((prev) =>
              prev.map((item) => (item.id === id ? { ...item, messages: formatted } : item))
            );
          }
        } catch (e) {
          logger.error('Failed to load chats for document:', e);
        }
      }
    }
    setIsProfileOpen(false);
  };

  const handleClearAllChats = () => {
    const newId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
      const r = (Math.random() * 16) | 0;
      return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
    });
    setSessionId(newId);
    localStorage.setItem('mediskye_session_id', newId);
    localStorage.removeItem('mediskye_conversations');
    setActivePdf(null);
    setConversations([{ id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId }]);
    showToast('info', 'Chat History Cleared');
  };

  const handleDeleteChat = (id, skipConfirm = false) => {
    const doDelete = () => {
      setConversations((prev) => {
        const newConversations = prev.filter((c) => c.id !== id);
        if (newConversations.length === 0) {
          const newId = 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
            const r = (Math.random() * 16) | 0;
            return (c === 'x' ? r : (r & 0x3) | 0x8).toString(16);
          });
          setSessionId(newId);
          localStorage.setItem('mediskye_session_id', newId);
          setActivePdf(null);
          return [{ id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId }];
        }
        if (id === sessionId) {
          const nextChat = newConversations[0];
          setSessionId(nextChat.id);
          localStorage.setItem('mediskye_session_id', nextChat.id);
          setActivePdf(nextChat.pdf || null);
        }
        return newConversations;
      });
      showToast('info', 'Chat Deleted');
    };

    if (skipConfirm) {
      doDelete();
    } else {
      logger.warn('handleDeleteChat called without skipConfirm. Falling back to immediate deletion.');
      doDelete();
    }
  };

  // B3 — inline rename handler
  const handleRenameChat = async (id, newTitle) => {
    const trimmed = newTitle.trim().slice(0, 60);
    if (!trimmed) return;

    // Optimistic local update
    setConversations((prev) =>
      prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c))
    );

    // If it has a real document_id, persist to backend
    const chat = conversations.find((c) => c.id === id);
    if (chat?.document_id) {
      try {
        await renameDocument(chat.document_id, trimmed);
        showToast('success', 'Chat Renamed', 'Chat renamed');
      } catch (err) {
        logger.error('Failed to rename document:', err);
        showToast('error', 'Rename Failed', err.message);
      }
    } else {
      showToast('info', 'Chat Renamed', 'Renamed locally (this chat has no server-side document)');
    }
  };

  const handleSetDarkMode = useCallback((val) => {
    const currentDark = resolveDarkMode(themePreference);
    const nextDark = typeof val === 'function' ? val(currentDark) : val;
    // An explicit light/dark toggle opts out of 'system' tracking.
    setThemePreference(nextDark ? 'dark' : 'light');
  }, [themePreference]);

  const handleDeleteAccount = async () => {
    try {
      await deleteAccount();
      localStorage.removeItem('token');
      localStorage.removeItem('mediskye_session_id');
      localStorage.removeItem('mediskye_patient_id');
      localStorage.removeItem('mediskye_conversations');
      if (currentUser?.id) {
        localStorage.removeItem(`mediskye_conversations_${currentUser.id}`);
      }
      setIsSettingsOpen(false);
      navigate('/login');
    } catch (err) {
      showToast('error', 'Deletion Failed', err.message || 'Could not delete your account.');
    }
  };

  return (
    <div className={`relative flex h-screen w-screen overflow-hidden transition-colors duration-200 ${
      darkMode ? 'bg-black text-slate-100' : 'bg-zinc-50 text-zinc-900'
    }`}>
      {/* Mobile overlay backdrop when open on < 768px */}
      {sidebarOpen && (
        <div
          data-testid="sidebar-backdrop"
          className="fixed inset-0 bg-black/50 z-30 md:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar container with DeepSeek-style GPU-accelerated slide */}
      <div
        data-testid="sidebar-wrapper"
        className={`fixed inset-y-0 left-0 z-40 w-72 flex-shrink-0 transition-transform duration-250 ease-in-out ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{ transitionDuration: '250ms' }}
      >
        <Sidebar
          isOpen={sidebarOpen}
          onToggle={toggleSidebar}
          conversations={conversations}
          activeSessionId={sessionId}
          onSelectChat={handleSelectChat}
          onDeleteChat={handleDeleteChat}
          onRenameChat={handleRenameChat}
          onNewChat={handleNewChat}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onOpenProfile={handleOpenProfile}
          darkMode={darkMode}
          setDarkMode={handleSetDarkMode}
          activePdf={activePdf}
          language={language}
          setLanguage={setLanguage}
          onLogout={handleLogout}
          currentUser={currentUser}
        />
      </div>

      <main
        className={`flex-1 flex flex-col h-full overflow-hidden relative transition-all duration-250 ease-in-out ${
          sidebarOpen ? 'md:ml-72' : 'md:ml-0'
        } ${darkMode ? 'bg-black' : 'bg-zinc-50'}`}
        style={{ transitionDuration: '250ms' }}
      >
        <ChatWindow
          sidebarOpen={sidebarOpen}
          toggleSidebar={toggleSidebar}
          messages={messages}
          isGenerating={isGenerating}
          onRegenerate={handleRegenerate}
          onSelectSource={(source) => setSelectedSource(source)}
          onSelectSampleQuery={handleSendMessage}
          onAttachFile={handleAttachFile}
          activePdf={activePdf}
          attachedDocuments={Array.isArray(currentChat.documents) && currentChat.documents.length > 0
            ? currentChat.documents
            : (activePdf ? [{ id: currentChat.document_id || 'doc-1', name: activePdf.name, filename: activePdf.name }] : [])}
          onDetachDocument={handleDetachDocument}
          onOpenUpload={() => {
            if (chatInputRef.current) chatInputRef.current.openFileUpload();
          }}
          documentId={currentChat.document_id}
          showToast={showToast}
          darkMode={darkMode}
          setDarkMode={handleSetDarkMode}
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handlePatientSelect}
          onOpenDependents={handleOpenDependents}
        />

        {uploadProgress && (
          <div className="max-w-3xl w-full mx-auto px-4 mb-2 animate-fade-in" data-testid="upload-progress-banner">
            <div className={`flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-xs font-medium border shadow-sm ${
              darkMode ? 'bg-zinc-900 border-zinc-800 text-zinc-300' : 'bg-blue-50/80 border-blue-200 text-blue-800'
            }`}>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
              </span>
              <span>{uploadProgress}</span>
            </div>
          </div>
        )}

        <ChatInput
          ref={chatInputRef}
          onSendMessage={handleSendMessage}
          onAttachFile={handleAttachFile}
          activeFile={activePdf}
          onRemoveFile={handleRemoveFile}
          isGenerating={isGenerating}
          onStopGeneration={handleStopGeneration}
          showToast={showToast}
          darkMode={darkMode}
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handlePatientSelect}
          onOpenDependents={handleOpenDependents}
        />
      </main>

      <DocumentModal source={selectedSource} onClose={() => setSelectedSource(null)} />

      <SettingsModal
        isOpen={isSettingsOpen}
        onClose={() => setIsSettingsOpen(false)}
        darkMode={darkMode}
        setDarkMode={handleSetDarkMode}
        themePreference={themePreference}
        setThemePreference={setThemePreference}
        onClearAllChats={handleClearAllChats}
        onDeleteAccount={handleDeleteAccount}
        onProfileUpdated={(updated) => setCurrentUser(updated)}
        language={language}
        setLanguage={setLanguage}
        showToast={showToast}
        currentUser={currentUser}
      />

      {isProfileOpen && (
        <Profile
          onClose={() => setIsProfileOpen(false)}
          showToast={showToast}
          darkMode={darkMode}
          initialTab={profileInitialTab}
          onProfileUpdated={refreshPatientContext}
        />
      )}

      <MemoryConsentModal
        isOpen={showMemoryConsentModal}
        onAllow={handleAllowMemory}
        onSkip={handleSkipMemory}
        darkMode={darkMode}
      />

      <Toast toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}
