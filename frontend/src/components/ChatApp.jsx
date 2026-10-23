import React, { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from './Sidebar';
import ChatWindow from './ChatWindow';
import ChatInput from './ChatInput';
import DocumentModal from './DocumentModal';
import SettingsModal from './SettingsModal';
import Profile from './Profile';
import MemoryConsentModal from './MemoryConsentModal';
import ExportModal from './ExportModal';
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
  deleteDocument,
  deleteAccount,
  updateProfile,
  getDocumentSummary,
} from '../services/api';
import { useNavigate } from 'react-router-dom';
import { logger } from '../services/logger';
import { speakText, stopSpeaking } from '../services/speech';

// ── Sample Lab Reports Pool ─────────────────────────────────
export const SAMPLE_REPORTS = [
  { path: '/samples/report-1.pdf', panel: 'Lipid Panel' },
  { path: '/samples/report-2.pdf', panel: 'Comprehensive Metabolic Panel' },
  { path: '/samples/report-3.pdf', panel: 'Thyroid Function' },
  { path: '/samples/report-4.pdf', panel: 'CBC' },
  { path: '/samples/report-5.pdf', panel: 'Diabetes Panel' },
];

// ── Theme: permanent Obsidian dark ─────────────────────────
function applyThemeToDOM() {
  document.documentElement.classList.add('dark');
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

  const [initialSessionId] = useState(() => generateSessionId());
  const [sessionId, setSessionId] = useState(initialSessionId);
  const sessionIdRef = useRef(sessionId);
  sessionIdRef.current = sessionId;
  const [loadingHistory, setLoadingHistory] = useState(false);
  const activeChatFetchRef = useRef(null);

  // ── Patient Context & User State ──
  const [currentUser, setCurrentUser] = useState(null);
  const [dependents, setDependents] = useState([]);
  const [selectedPatientId, setSelectedPatientId] = useState(() => {
    return localStorage.getItem('mediskye_patient_id') || 'self';
  });
  const [profileInitialTab, setProfileInitialTab] = useState('profile');

  // ── Theme state: 'light' | 'dark' | 'system' — the raw preference is persisted ──
  // Permanent Obsidian dark theme — light mode has been removed.
  const themePreference = 'dark';
  const darkMode = true;
  const setThemePreference = useCallback(() => {}, []);
  const [language, setLanguage] = useState('English');

  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 768) {
      return false;
    }
    return localStorage.getItem('mediskye_sidebar_open') !== 'false';
  });

  // Auto-read AI responses aloud (persisted UI preference, no server round-trip)
  const [autoRead, setAutoRead] = useState(() => {
    try {
      return localStorage.getItem('mediskye_auto_read') === 'true';
    } catch {
      return false;
    }
  });

  const setAutoReadPersist = (val) => {
    setAutoRead(Boolean(val));
    try {
      localStorage.setItem('mediskye_auto_read', String(Boolean(val)));
    } catch (e) {
      logger.error('Failed to persist auto-read preference:', e);
    }
  };

  const toggleSidebar = () => {
    const next = !sidebarOpen;
    setSidebarOpen(next);
    localStorage.setItem('mediskye_sidebar_open', String(next));
  };
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState(null);

  const [activePdf, setActivePdf] = useState(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExportingSummary, setIsExportingSummary] = useState(false);
  const [printSummaryText, setPrintSummaryText] = useState('');
  const [uploadProgress, setUploadProgress] = useState(null);
  const abortControllerRef = useRef(null);
  const isSubmittingRef = useRef(false);
  const isMountedRef = useRef(true);
  const chatInputRef = useRef(null);

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      stopSpeaking();
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
        abortControllerRef.current = null;
      }
    };
  }, []);

  // ── Connection status watcher ──
  useEffect(() => {
    const handleOffline = () => {
      logger.warn('Connection lost: client is offline.');
    };
    const handleOnline = () => {
      logger.info('Connection restored: client is online.');
    };
    window.addEventListener('offline', handleOffline);
    window.addEventListener('online', handleOnline);
    return () => {
      window.removeEventListener('offline', handleOffline);
      window.removeEventListener('online', handleOnline);
    };
  }, []);

  // Clean up legacy localStorage chat caches on mount
  useEffect(() => {
    try {
      localStorage.removeItem('mediskye_conversations');
      localStorage.removeItem('mediskye_session_id');
      localStorage.removeItem('mediskye_last_active_user');
    } catch (e) {}
  }, []);

  // In-memory conversation state (Neon DB is the single source of truth)
  const [conversations, setConversations] = useState(() => [
    { id: initialSessionId, title: 'New Conversation', messages: [], pdf: null, patient_id: 'self' },
  ]);

  // Load chat history from backend with race condition protection
  const loadChatHistory = useCallback(async (targetDocId, targetSessionId) => {
    const fetchKey = targetDocId || targetSessionId;
    activeChatFetchRef.current = fetchKey;
    setLoadingHistory(true);
    try {
      const chats = await getDocumentChats(targetDocId);
      // Guard against race conditions if user clicked rapidly between two documents
      if (activeChatFetchRef.current !== fetchKey || (targetSessionId && sessionIdRef.current !== targetSessionId)) {
        return;
      }
      const formatted = Array.isArray(chats)
        ? chats.map((c) => ({
            id: c.id,
            sender: c.role === 'ai' ? 'assistant' : 'user',
            text: c.message,
            timestamp: c.created_at
              ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : '',
          }))
        : [];

      setConversations((prev) =>
        prev.map((item) => {
          const isTarget = item.id === targetSessionId || (targetDocId && (item.id === targetDocId || item.document_id === targetDocId));
          if (!isTarget) return item;
          if (!targetDocId && (!formatted || formatted.length === 0) && item.messages && item.messages.length > 0) {
            return item;
          }
          return { ...item, messages: formatted };
        })
      );
    } catch (e) {
      logger.error('Failed to load chat history from backend:', e);
    } finally {
      if (activeChatFetchRef.current === fetchKey) {
        setLoadingHistory(false);
      }
    }
  }, []);

  // Load User, Dependents, and Documents simultaneously on Mount (Bug 10 & Bug 1)
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

  // Reusable document refresher: synchronizes server document truth with local state
  const refreshDocuments = useCallback(async (activeDocId = null, overrideTitle = null) => {
    try {
      const docs = await getUserDocuments();
      if (!Array.isArray(docs)) return [];

      let effectiveDocs = [...docs];

      setConversations((prev) => {
        if (activeDocId && !effectiveDocs.some((d) => d.id === activeDocId)) {
          const match = prev.find((c) => c.id === activeDocId || c.document_id === activeDocId);
          if (match?.pdf) {
            effectiveDocs.push({
              id: activeDocId,
              filename: match.pdf.name || match.pdf.filename || 'report.pdf',
              title: overrideTitle || match.title,
              created_at: match.created_at || new Date().toISOString(),
            });
          }
        }

        if (effectiveDocs.length === 0) {
          const nonDocConvs = prev.filter((c) => !c.document_id && !c.pdf);
          if (nonDocConvs.length > 0) return nonDocConvs;
          return [{ id: sessionIdRef.current, title: 'New Conversation', messages: [], pdf: null, patient_id: 'self' }];
        }

        const existingMap = new Map();
        prev.forEach((c) => {
          if (c.id) existingMap.set(c.id, c);
          if (c.document_id) existingMap.set(c.document_id, c);
        });

        const syncedDocConvs = effectiveDocs.map((doc) => {
          const existing = existingMap.get(doc.id);
          const pdfMeta = {
            id: doc.id,
            name: doc.filename,
            filename: doc.filename,
            size: 8192,
          };
          const resolvedDocTitle = (activeDocId && doc.id === activeDocId && overrideTitle)
            ? overrideTitle
            : doc.title;

          let messages = existing?.messages || [];

          if (existing) {
            return {
              ...existing,
              id: doc.id,
              document_id: doc.id,
              patient_id: doc.dependent_id || existing.patient_id || 'self',
              title: resolvedDocTitle || (existing.title && existing.title !== 'New Conversation' && existing.title !== 'New chat'
                ? existing.title
                : 'New Chat'),
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
            title: resolvedDocTitle || 'New Chat',
            messages,
            pdf: pdfMeta,
            documents: [pdfMeta],
            created_at: doc.created_at,
          };
        });

        // Retain only genuinely non-document conversations with messages when documents exist (Bug 8)
        const nonDocConvs = prev.filter(
          (c) => !c.document_id && !c.pdf && !effectiveDocs.some((d) => d.id === c.id) && Array.isArray(c.messages) && c.messages.length > 0
        );

        return [...syncedDocConvs, ...nonDocConvs];
      });

      const targetDocId = activeDocId || effectiveDocs[0]?.id;
      if (targetDocId && effectiveDocs.length > 0) {
        const targetDoc = effectiveDocs.find((d) => d.id === targetDocId) || effectiveDocs[0];
        const pdfMeta = {
          id: targetDoc.id,
          name: targetDoc.filename,
          filename: targetDoc.filename,
          size: 8192,
        };
        setActivePdf(pdfMeta);
        setSessionId(targetDoc.id);

        loadChatHistory(targetDoc.id, targetDoc.id);
      } else {
        setActivePdf(null);
        loadChatHistory(null, sessionIdRef.current);
      }

      return docs;
    } catch (err) {
      logger.error('Failed to refresh documents:', err);
      return [];
    }
  }, [loadChatHistory]);

  // Synchronize with server truth on account load / refresh (Neon DB single source of truth)
  useEffect(() => {
    if (currentUser?.id) {
      if (userLoadedRef.current === currentUser.id) return;
      userLoadedRef.current = currentUser.id;

      refreshDocuments().then((docs) => {
        if (!docs || docs.length === 0) {
          setActivePdf(null);
          loadChatHistory(null, sessionIdRef.current);
        }
      }).catch(() => {
        setActivePdf(null);
      });
    }
  }, [currentUser, refreshDocuments, loadChatHistory]);

  // ── Enforce permanent dark theme on the DOM ──
  useEffect(() => {
    applyThemeToDOM('dark');
    try {
      localStorage.setItem('mediskye_theme', 'dark');
      localStorage.setItem('theme', 'dark');
    } catch (e) {
      logger.error('Failed to persist theme preference:', e);
    }
  }, []);

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
    } catch (err) {
      logger.error('Failed to update memory consent:', err);
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

  const handlePatientSelect = (patientId) => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    stopSpeaking();
    setIsGenerating(false);
    isSubmittingRef.current = false;
    setSelectedPatientId(patientId);
    localStorage.setItem('mediskye_patient_id', patientId);
  };

  const handleOpenDependents = () => {
    setProfileInitialTab('dependents');
    setIsProfileOpen(true);
  };

  const handleOpenProfile = () => {
    setProfileInitialTab('profile');
    setIsProfileOpen(true);
  };

  const handleAttachFile = async (file, options = {}) => {
    if (!file) return null;
    const { customTitle = null } = options;

    if (typeof performance !== 'undefined' && performance.mark) {
      performance.mark('upload_file_selected');
    }

    const isValidType =
      file.type === 'application/pdf' ||
      file.name.match(/\.(pdf|jpg|jpeg|png)$/i);
    if (!isValidType) {
      console.error('Invalid File Format: Please upload a PDF, JPG, or PNG file.');
      return null;
    }

    const maxMb = 50;
    if (file.size > maxMb * 1024 * 1024) {
      console.error(`File Too Large: Maximum allowed file size is ${maxMb}MB.`);
      return null;
    }

    setIsGenerating(true);

    try {
      if (typeof performance !== 'undefined' && performance.mark) {
        performance.mark('upload_request_sent');
        try {
          performance.measure('file_prep_to_request', 'upload_file_selected', 'upload_request_sent');
          const m = performance.getEntriesByName('file_prep_to_request').pop();
          if (import.meta.env.DEV) {
            console.info(`[UPLOAD_TIMING] file_prep_to_request: ${m?.duration?.toFixed(2)}ms`);
          }
        } catch {}
      }

      const data = customTitle
        ? await uploadPdfReport(file, selectedPatientId, sessionId, customTitle)
        : await uploadPdfReport(file, selectedPatientId, sessionId);

      if (typeof performance !== 'undefined' && performance.mark) {
        performance.mark('upload_job_id_received');
        try {
          performance.measure('request_to_job_id', 'upload_request_sent', 'upload_job_id_received');
          const m = performance.getEntriesByName('request_to_job_id').pop();
          if (import.meta.env.DEV) {
            console.info(`[UPLOAD_TIMING] request_to_job_id: ${m?.duration?.toFixed(2)}ms (job_id: ${data?.job_id || data?.document_id})`);
          }
        } catch {}
      }

      let newDocId = null;
      if (data?.job_id) {
        const jobId = data.job_id;
        const startTime = Date.now();
        // Fast-start polling: the backend flips the job to COMPLETED as soon as the
        // vector index is local_ready (Step A). Poll quickly at first so the UI
        // unlocks within ~0.5s of that flip, then back off to the steady interval.
        // We intentionally never wait for index_status === 'synced' or for
        // metrics/summary pre-warming — those run in the background (Step B).
        const POLL_INTERVAL = (typeof window !== 'undefined' && window.__POLL_INTERVAL__) || 2000;
        const pollDelays = (typeof window !== 'undefined' && window.__POLL_INTERVAL__)
          ? [POLL_INTERVAL]
          : [500, 500, 1000, 1000];
        const MAX_WAIT = (typeof window !== 'undefined' && window.__UPLOAD_MAX_WAIT__) || 120000;
        let consecutiveFailures = 0;
        const MAX_CONSECUTIVE_FAILURES = 5;
        let hasRecordedFirstPoll = false;
        let pollIndex = 0;

        while (isMountedRef.current && Date.now() - startTime < MAX_WAIT) {
          const delay = pollIndex < pollDelays.length ? pollDelays[pollIndex] : POLL_INTERVAL;
          pollIndex += 1;
          await new Promise((r) => setTimeout(r, delay));

          if (!hasRecordedFirstPoll && typeof performance !== 'undefined' && performance.mark) {
            hasRecordedFirstPoll = true;
            performance.mark('first_status_poll');
            try {
              performance.measure('job_id_to_first_poll', 'upload_job_id_received', 'first_status_poll');
              const m = performance.getEntriesByName('job_id_to_first_poll').pop();
              if (import.meta.env.DEV) {
                console.info(`[UPLOAD_TIMING] job_id_to_first_poll: ${m?.duration?.toFixed(2)}ms`);
              }
            } catch {}
          }

          let status;
          try {
            status = await getUploadStatus(jobId, 10000);
            consecutiveFailures = 0;
          } catch (err) {
            consecutiveFailures += 1;
            logger.warn(`Upload status poll failed (${consecutiveFailures}/${MAX_CONSECUTIVE_FAILURES}):`, err);

            if (consecutiveFailures >= MAX_CONSECUTIVE_FAILURES) {
              await refreshDocuments();
              console.error('Upload Status Lost: Could not confirm upload status.');
              return null;
            }
            continue;
          }

          if (status.status === 'completed') {
            newDocId = status.document_id;
            if (typeof performance !== 'undefined' && performance.mark) {
              performance.mark('status_completed');
              try {
                performance.measure('first_poll_to_completed', 'first_status_poll', 'status_completed');
                performance.measure('total_upload_e2e', 'upload_file_selected', 'status_completed');
                const mPoll = performance.getEntriesByName('first_poll_to_completed').pop();
                const mTotal = performance.getEntriesByName('total_upload_e2e').pop();
                if (import.meta.env.DEV) {
                  console.info(`[UPLOAD_TIMING] first_poll_to_completed: ${mPoll?.duration?.toFixed(2)}ms | total_upload_e2e: ${mTotal?.duration?.toFixed(2)}ms`);
                }
              } catch {}
            }
            break;
          }

          if (status.status === 'failed') {
            throw new Error(status.error || 'Upload processing failed');
          }

          setUploadProgress('Processing report...');
        }

        if (!newDocId) {
          await refreshDocuments();
          console.warn('Upload Taking Longer Than Expected: polling deadline expired.');
          return null;
        }
      } else if (data?.document_id) {
        newDocId = data.document_id;
      } else {
        throw new Error('Upload failed: no job_id or document_id received');
      }

      const pdfMeta = { id: newDocId, name: file.name, filename: file.name, size: file.size };
      // Unlock the UI the moment the job is COMPLETED — the document list sync
      // below is a background reconciliation and must not keep the spinner up.
      setUploadProgress(null);
      setIsGenerating(false);
      setActivePdf(pdfMeta);

      const autoTitle = customTitle || cleanFilename(file.name);
      if (customTitle && newDocId) {
        renameDocument(newDocId, customTitle).catch(() => {});
      }

      // Promote the conversation's id to the server's document_id so the
      // sidebar entry is stable across sessions (re-login fetches by doc.id).
      const prevSessionId = sessionId;
      setSessionId(newDocId);
      sessionIdRef.current = newDocId;

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
            title: customTitle
              ? customTitle
              : ((current.title === 'New Conversation' || current.title === 'New chat') ? autoTitle : current.title),
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
      await refreshDocuments(newDocId, customTitle);

      // Bug 8: Ensure the newly uploaded document replaces any empty "New Conversation"
      setConversations((prev) => {
        return prev.filter((c) => {
          if (c.id === newDocId || c.document_id === newDocId) return true;
          const hasMessages = Array.isArray(c.messages) && c.messages.length > 0;
          const hasDoc = Boolean(c.document_id || c.pdf);
          return hasMessages || hasDoc;
        });
      });

      return newDocId;
    } catch (err) {
      logger.error('Upload Failed:', err);
      return null;
    } finally {
      setUploadProgress(null);
      setIsGenerating(false);
    }
  };

  const handleDetachDocument = async (docId) => {
    try {
      await deleteDocument(docId).catch(() => {});
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
    } catch (err) {
      logger.error('Detach Failed:', err);
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
    if (!userQuery || isSubmittingRef.current || isGenerating) return;
    isSubmittingRef.current = true;
    const { appendUserMessage = true, docIdOverride = null, preserveTitle = null } = options;

    // Any new question immediately silences previously spoken answers.
    stopSpeaking();

    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    const userMsgId = `user-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
    const assistantMsgId = `asst-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;

    const userMsgObj = {
      id: userMsgId,
      sender: 'user',
      text: userQuery,
      timestamp,
    };

    const assistantMsgObj = {
      id: assistantMsgId,
      sender: 'assistant',
      text: '',
      status: 'Analyzing your question...',
      isStreaming: true,
      timestamp,
    };

    // Bug 9 Fix: Atomically create user bubble AND assistant placeholder in one update
    const activeTargetId = docIdOverride || sessionId;
    if (docIdOverride) {
      sessionIdRef.current = docIdOverride;
    }
    const prevChat = conversations.find((c) => c.id === activeTargetId);
    const prevTitle = preserveTitle || prevChat?.title || 'New Conversation';
    const newMessages = appendUserMessage ? [userMsgObj, assistantMsgObj] : [assistantMsgObj];
    setConversations((prev) => {
      const matchExists = prev.some((c) => c.id === activeTargetId);
      if (!matchExists) {
        return [
          {
            id: activeTargetId,
            document_id: docIdOverride || null,
            title: preserveTitle || ((appendUserMessage && userQuery) ? autoNameFromQuery(userQuery) : 'New Conversation'),
            messages: newMessages,
            pdf: null,
            documents: [],
            patient_id: selectedPatientId,
          },
          ...prev,
        ];
      }
      return prev.map((c) =>
        c.id === activeTargetId
          ? {
              ...c,
              title: preserveTitle
                ? preserveTitle
                : ((appendUserMessage && (c.title === 'New Conversation' || c.title === 'New chat'))
                  ? autoNameFromQuery(userQuery)
                  : c.title),
              messages: [...c.messages, ...newMessages],
            }
          : c
      );
    });

    setIsGenerating(true);
    const controller = new AbortController();
    abortControllerRef.current = controller;

    let isConflict = false;
    try {
      // Read document ID from current conversation
      let chatDocId = docIdOverride || null;
      let chatPatientId = selectedPatientId;
      const chatObj = conversations.find((c) => c.id === activeTargetId);
      if (!chatDocId) chatDocId = chatObj?.document_id || null;
      if (chatObj?.patient_id) chatPatientId = chatObj.patient_id;

      // Bug 9 Fix: Stream query chunks directly to assistantMsgId ONLY
      let assistantAccum = '';
      let hadStreamError = false;
      await sendQueryStream(userQuery, chatDocId || activeTargetId, language, (chunk) => {
        // Guard against race conditions if user switched active document mid-stream
        if (sessionIdRef.current !== activeTargetId) {
          return;
        }

        if (chunk.chunk || chunk.token) {
          assistantAccum += chunk.chunk || chunk.token || '';
        }
        if (chunk.error) {
          hadStreamError = true;
        }
        setConversations((prev) => {
          return prev.map((c) => {
            if (c.id !== activeTargetId && c.document_id !== activeTargetId) return c;
            const updatedChat = { ...c };
            if (preserveTitle) {
              updatedChat.title = preserveTitle;
            } else if (chunk.title && !c.title?.startsWith('Sample Report:')) {
              updatedChat.title = chunk.title;
            }
            const targetIdx = c.messages.findIndex((m) => m.id === assistantMsgId);
            if (targetIdx === -1) return updatedChat;

            const targetMsg = { ...c.messages[targetIdx] };
            if (chunk.stage && chunk.message) {
              targetMsg.status = chunk.message;
            } else if (chunk.specialists) {
              targetMsg.specialists = chunk.specialists;
            } else if (chunk.chunk || chunk.token) {
              targetMsg.text = (targetMsg.text || '') + (chunk.chunk || chunk.token);
              targetMsg.status = null;
            } else if (chunk.error) {
              targetMsg.error = chunk.error || 'Something went wrong. Tap to retry.';
              targetMsg.status = null;
              targetMsg.isStreaming = false;
            }

            const updatedMsgs = [...c.messages];
            updatedMsgs[targetIdx] = targetMsg;
            updatedChat.messages = updatedMsgs;
            return updatedChat;
          });
        });
      }, chatPatientId, controller.signal);

      // Auto-read: speak the finished answer aloud when enabled.
      if (autoRead && !hadStreamError && assistantAccum.trim()) {
        speakText(assistantAccum, undefined, language);
      }

    } catch (err) {
      if (err && err.name === 'AbortError') {
        // User stopped generation — keep any partial text, skip the error toast.
      } else if (err?.status === 409 || err?.message?.includes('already active')) {
        isConflict = true;
        console.warn('A response is already generating. Please wait for it to finish.');
        // Do NOT render a second user bubble or an error state in the chat; remove the newly added messages
        setConversations((prev) => {
          return prev.map((c) => {
            if (c.id !== activeTargetId) return c;
            return {
              ...c,
              title: prevTitle,
              messages: c.messages.filter((m) => m.id !== userMsgId && m.id !== assistantMsgId),
            };
          });
        });
      } else {
        logger.error('Query Error:', err);
        setConversations((prev) => {
          return prev.map((c) => {
            if (c.id !== activeTargetId) return c;
            const targetIdx = c.messages.findIndex((m) => m.id === assistantMsgId);
            if (targetIdx === -1) return c;

            const targetMsg = { ...c.messages[targetIdx] };
            targetMsg.error = err.message;
            targetMsg.status = null;
            targetMsg.isStreaming = false;

            const updatedMsgs = [...c.messages];
            updatedMsgs[targetIdx] = targetMsg;
            return { ...c, messages: updatedMsgs };
          });
        });
      }
    } finally {
      if (!isConflict) {
        setConversations((prev) => {
          return prev.map((c) => {
            if (c.id !== activeTargetId) return c;
            const targetIdx = c.messages.findIndex((m) => m.id === assistantMsgId);
            if (targetIdx === -1) return c;

            const targetMsg = { ...c.messages[targetIdx] };
            targetMsg.isStreaming = false;
            targetMsg.status = null;

            const updatedMsgs = [...c.messages];
            updatedMsgs[targetIdx] = targetMsg;
            return { ...c, messages: updatedMsgs };
          });
        });
        setIsGenerating(false);
        abortControllerRef.current = null;
      }
      isSubmittingRef.current = false;
    }
  };

  const handleStopGeneration = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopSpeaking();
    setIsGenerating(false);
  };

  const handleExportSummary = async () => {
    if (isExportingSummary) return printSummaryText;
    setIsExportingSummary(true);

    let summaryTextToUse = '';
    const activeDocId = currentChat?.document_id || activePdf?.id;
    const currentMsgs = currentChat?.messages || messages || [];
    const assistantMsgs = currentMsgs.filter((m) => m.sender === 'assistant');
    const fallbackText = assistantMsgs.length > 0 ? assistantMsgs[assistantMsgs.length - 1].text : '';

    if (activeDocId) {
      try {
        const data = await getDocumentSummary(activeDocId);
        if (data && data.summary && data.summary.trim()) {
          summaryTextToUse = data.summary.trim();
        }
      } catch (err) {
        logger.warn('Failed to fetch cached document summary, falling back:', err);
      }
    }

    const finalSummary = (summaryTextToUse && summaryTextToUse.trim()) ? summaryTextToUse : fallbackText;
    setPrintSummaryText(finalSummary);
    setIsExportingSummary(false);
    return finalSummary;
  };

  const handleRegenerate = () => {
    if (isGenerating) return;
    const lastUserMsg = [...messages].reverse().find((m) => m.sender === 'user');
    if (!lastUserMsg) return;

    // Regenerating replaces the answer — silence anything still being spoken.
    stopSpeaking();

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
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopSpeaking();
    setIsGenerating(false);
    isSubmittingRef.current = false;

    const newId = generateSessionId();
    setSessionId(newId);
    setActivePdf(null);
    setIsProfileOpen(false);
    setConversations((prev) => [
      { id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId },
      ...prev,
    ]);
  };

  const handleSampleReportClick = async () => {
    if (isGenerating || isSubmittingRef.current) return;
    const chosen = SAMPLE_REPORTS[Math.floor(Math.random() * SAMPLE_REPORTS.length)];
    const customTitle = `Sample Report: ${chosen.panel}`;
    try {
      let blob;
      try {
        const res = await fetch(chosen.path);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        blob = await res.blob();
      } catch (_) {
        blob = new Blob([`%PDF-1.4 Sample ${chosen.panel} Report`], { type: 'application/pdf' });
      }
      const sampleFile = new File([blob], 'Sample_Report.pdf', { type: 'application/pdf' });
      const newDocId = await handleAttachFile(sampleFile, { customTitle });
      if (newDocId) {
        await handleSendMessage('Can you summarize the abnormal findings in this report?', {
          docIdOverride: newDocId,
          preserveTitle: customTitle,
        });
      }
    } catch (err) {
      logger.error('Sample Report Failed:', err);
    }
  };

  const handleSelectChat = async (id) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopSpeaking();
    setIsGenerating(false);
    isSubmittingRef.current = false;

    setSessionId(id);
    const chat = conversations.find((c) => c.id === id);
    if (chat) {
      setActivePdf(chat.pdf || null);
      if (chat.patient_id) {
        setSelectedPatientId(chat.patient_id);
      }
      const targetDocId = chat.document_id || (chat.pdf ? id : null);
      await loadChatHistory(targetDocId, id);
    } else {
      await loadChatHistory(null, id);
    }
    setIsProfileOpen(false);
  };

  const handleClearAllChats = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopSpeaking();
    setIsGenerating(false);
    isSubmittingRef.current = false;

    const newId = generateSessionId();
    setSessionId(newId);
    setActivePdf(null);
    setConversations([{ id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId }]);
  };

  const handleDeleteChat = async (id, skipConfirm = false) => {
    try {
      const chat = conversations.find((c) => c.id === id);
      const targetDocId = chat?.document_id || (chat?.pdf ? id : null);
      if (targetDocId) {
        await deleteDocument(targetDocId);
      }

      setConversations((prev) => {
        const newConversations = prev.filter((c) => c.id !== id && c.document_id !== targetDocId);
        if (newConversations.length === 0) {
          const newId = generateSessionId();
          setSessionId(newId);
          setActivePdf(null);
          return [{ id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId }];
        }
        if (id === sessionId || (targetDocId && targetDocId === sessionId)) {
          const nextChat = newConversations[0];
          setSessionId(nextChat.id);
          setActivePdf(nextChat.pdf || null);
          const nextDocId = nextChat.document_id || (nextChat.pdf ? nextChat.id : null);
          loadChatHistory(nextDocId, nextChat.id);
        }
        return newConversations;
      });

      await refreshDocuments();
    } catch (err) {
      logger.error('Delete failed:', err);
    }
  };

  // B3 — inline rename handler
  const handleRenameChat = async (id, newTitle) => {
    const trimmed = newTitle.trim().slice(0, 60);
    if (!trimmed) return;

    const chat = conversations.find((c) => c.id === id);
    const targetDocId = chat?.document_id || (chat?.pdf ? id : null);

    // If it has a real document_id, persist to backend first
    if (targetDocId) {
      try {
        const res = await renameDocument(targetDocId, trimmed);
        const savedTitle = res?.title || trimmed;
        setConversations((prev) =>
          prev.map((c) => (c.id === id ? { ...c, title: savedTitle } : c))
        );
        await refreshDocuments();
      } catch (err) {
        logger.error('Failed to rename document:', err);
      }
    } else {
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c))
      );
    }
  };

  // Theme is locked to dark; kept as a no-op for child component prop contracts.
  const handleSetDarkMode = useCallback(() => {}, []);

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
      logger.error('Deletion Failed:', err);
    }
  };

  return (
    <div className={`relative flex h-dvh w-screen overflow-hidden transition-colors duration-200 ${
      darkMode ? 'bg-[#07090e] text-slate-100' : 'bg-zinc-50 text-zinc-900'
    }`}>
      {/* Mobile overlay backdrop when open on < 768px */}
      {sidebarOpen && (
        <div
          data-testid="sidebar-backdrop"
          className="fixed inset-0 bg-black/60 backdrop-blur-xs z-30 md:hidden"
          onClick={toggleSidebar}
        />
      )}

      {/* Sidebar container with DeepSeek-style GPU-accelerated slide */}
      <div
        data-testid="sidebar-wrapper"
        className={`fixed inset-y-0 left-0 z-40 w-72 md:w-64 flex-shrink-0 transition-transform duration-250 ease-in-out ${
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
          sidebarOpen ? 'md:ml-64' : 'md:ml-0'
        } ${darkMode ? 'bg-[#07090e]' : 'bg-zinc-50'}`}
        style={{ transitionDuration: '250ms' }}
      >
        <ChatWindow
          sidebarOpen={sidebarOpen}
          toggleSidebar={toggleSidebar}
          messages={messages}
          isGenerating={isGenerating}
          loadingHistory={loadingHistory}
          onRegenerate={handleRegenerate}
          onSelectSampleQuery={handleSendMessage}
          onTrySampleReport={handleSampleReportClick}
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
          darkMode={darkMode}
          setDarkMode={handleSetDarkMode}
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handlePatientSelect}
          onOpenDependents={handleOpenDependents}
          isExportingSummary={isExportingSummary}
          printSummaryText={printSummaryText}
          onExportSummary={handleExportSummary}
          onOpenExport={() => setIsExportOpen(true)}
        />

        {uploadProgress && (
          <div className="max-w-3xl w-full mx-auto px-4 mb-2 animate-fade-in" data-testid="upload-progress-banner">
            <div className={`flex items-center gap-2.5 px-3.5 py-2 rounded-xl text-xs font-medium border shadow-sm ${
              darkMode ? 'bg-[#0e131b] border-white/[0.08] text-slate-300' : 'bg-blue-50/80 border-blue-200 text-blue-800'
            }`}>
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-cyan-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-2 w-2 bg-cyan-500" />
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
          attachedDocuments={Array.isArray(currentChat.documents) && currentChat.documents.length > 0
            ? currentChat.documents
            : (activePdf ? [{ id: currentChat.document_id || activePdf.id || 'doc-1', name: activePdf.name, filename: activePdf.name }] : [])}
          onDetachDocument={handleDetachDocument}
          onRemoveFile={handleRemoveFile}
          isGenerating={isGenerating}
          onStopGeneration={handleStopGeneration}
          darkMode={darkMode}
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handlePatientSelect}
          onOpenDependents={handleOpenDependents}
        />
      </main>

      <DocumentModal source={selectedSource} onClose={() => setSelectedSource(null)} />

      <ExportModal
        isOpen={isExportOpen}
        onClose={() => setIsExportOpen(false)}
        darkMode={darkMode}
        documentId={currentChat.document_id || null}
        documentTitle={currentChat.title || (activePdf ? activePdf.name : null)}
        messages={messages}
        user={currentUser}
      />

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
        currentUser={currentUser}
        autoRead={autoRead}
        setAutoRead={setAutoReadPersist}
        onOpenProfile={handleOpenProfile}
      />

      {isProfileOpen && (
        <Profile
          onClose={() => setIsProfileOpen(false)}
          darkMode={darkMode}
          initialTab={profileInitialTab}
          onProfileUpdated={refreshPatientContext}
          profile={currentUser}
          dependents={dependents}
        />
      )}

      <MemoryConsentModal
        isOpen={showMemoryConsentModal}
        onAllow={handleAllowMemory}
        onSkip={handleSkipMemory}
        darkMode={darkMode}
      />
    </div>
  );
}
