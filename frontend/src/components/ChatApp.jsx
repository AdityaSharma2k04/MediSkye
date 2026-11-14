import React, { useState, useEffect, useCallback, useRef, useMemo, lazy, Suspense } from 'react';
import { useTranslation } from 'react-i18next';
import Sidebar from './Sidebar';
import DocumentModal from './DocumentModal';
import MemoryConsentModal from './MemoryConsentModal';
import Workbench from './workbench/Workbench';
import NavRail from './workbench/NavRail';
import CommandPalette from './workbench/CommandPalette';
import { buildPatients, isSelfSelected } from './workbench/PatientSwitcher';
import useViewport from '../hooks/useViewport';
import useHotkeys from '../hooks/useHotkeys';
import useLabMetrics, { invalidateMetrics } from '../hooks/useLabMetrics';
import useTrendData from '../hooks/useTrendData';
import { STORAGE_KEYS, readStorage, writeStorage } from '../lib/storageKeys';
import { metricKey, metricName } from '../lib/clinical';
import { cn } from '../lib/cn';

// Lazy-loaded modal chunks for fast initial boot + 0ms idle preloading
const SettingsModal = lazy(() => import('./SettingsModal'));
const Profile = lazy(() => import('./Profile'));
const ExportModal = lazy(() => import('./ExportModal'));
const MemoryVault = lazy(() => import('./workbench/MemoryVault'));

function preloadModals() {
  import('./SettingsModal');
  import('./Profile');
  import('./ExportModal');
  import('./workbench/MemoryVault');
}
import {
  uploadPdfReport,
  getUploadStatus,
  sendQueryStream,
  logout,
  getProfile,
  getDependents,
  getUserDocuments,
  getDocumentChats,
  getGeneralChats,
  renameDocument,
  deleteDocument,
  renameChatSession,
  deleteChatSession,
  clearAllChatSessions,
  deleteAccount,
  updateProfile,
  getDocumentSummary,
  getCachedProfile,
  getCachedDependents,
  getCachedDocuments,
  setCachedDocuments,
  getCachedConversations,
  setCachedConversations,
  prewarmPatientLocalCache,
  getMemoryFacts,
  getMetricTrends,
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
    invalidateMetrics();
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
  const [currentUser, setCurrentUser] = useState(() => (typeof getCachedProfile === 'function' ? getCachedProfile() : null));
  const [dependents, setDependents] = useState(() => (typeof getCachedDependents === 'function' ? getCachedDependents() || [] : []));
  const [selectedPatientId, setSelectedPatientId] = useState(() => {
    return localStorage.getItem('mediskye_patient_id') || 'self';
  });
  const [profileInitialTab, setProfileInitialTab] = useState('profile');

  // Cross-Tab Patient Profile Sync
  useEffect(() => {
    const handleStorage = (e) => {
      if (e.key === 'mediskye_patient_id' && e.newValue) {
        setSelectedPatientId(e.newValue);
      }
    };
    window.addEventListener('storage', handleStorage);
    return () => window.removeEventListener('storage', handleStorage);
  }, []);

  // ── Theme state: 'light' | 'dark' | 'system' — the raw preference is persisted ──
  // Permanent Obsidian dark theme — light mode has been removed.
  const themePreference = 'dark';
  const darkMode = true;
  const setThemePreference = useCallback(() => {}, []);
  const [language, setLanguage] = useState('English');

  // Desktop (≥1024): open unless the user collapsed it. Tablet/phone: closed drawer.
  const [sidebarOpen, setSidebarOpen] = useState(() => {
    if (typeof window !== 'undefined' && window.innerWidth < 1024) {
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

  const closeSidebarOnSmallScreens = () => {
    if (typeof window !== 'undefined' && window.innerWidth < 1024) setSidebarOpen(false);
  };
  const [isSettingsOpen, setIsSettingsOpen] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isExportOpen, setIsExportOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [selectedSource, setSelectedSource] = useState(null);

  const [activePdf, setActivePdf] = useState(() => {
    try {
      const initPatId = localStorage.getItem('mediskye_patient_id') || 'self';
      const cachedConvs = typeof getCachedConversations === 'function' ? getCachedConversations(initPatId) : null;
      if (Array.isArray(cachedConvs)) {
        const found = cachedConvs.find((c) => c.pdf || c.document_id);
        if (found?.pdf) return found.pdf;
      }
      const cachedDocs = typeof getCachedDocuments === 'function' ? getCachedDocuments(initPatId) : null;
      if (Array.isArray(cachedDocs) && cachedDocs.length > 0) {
        const doc = cachedDocs[0];
        return {
          id: doc.id,
          name: doc.filename,
          filename: doc.filename,
          title: doc.title,
          collected_at: doc.collected_at,
          is_future_collection_date: doc.is_future_collection_date,
          size: 8192,
        };
      }
    } catch (_) {}
    return null;
  });
  const [viewMode, setViewMode] = useState('chat');
  const [isGenerating, setIsGenerating] = useState(false);
  const [isExportingSummary, setIsExportingSummary] = useState(false);
  const [printSummaryText, setPrintSummaryText] = useState('');
  const [uploadProgress, setUploadProgress] = useState(null);
  // Structured pipeline state for the two-phase UploadStepper
  const [uploadState, setUploadState] = useState(null);
  const uploadTimersRef = useRef([]);
  const clearUploadTimers = () => {
    uploadTimersRef.current.forEach((id) => clearTimeout(id));
    uploadTimersRef.current = [];
  };
  useEffect(() => () => clearUploadTimers(), []);
  const [uploadError, setUploadError] = useState(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncToast, setSyncToast] = useState(null);
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

  const handleManualCloudSyncRef = useRef(null);

  const [isOnline, setIsOnline] = useState(() => (typeof navigator !== 'undefined' ? navigator.onLine : true));

  useEffect(() => {
    const handleOnline = () => {
      setIsOnline(true);
      if (typeof handleManualCloudSyncRef.current === 'function') {
        handleManualCloudSyncRef.current().catch(() => {});
      }
    };
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  // Preload lazy modal chunks in background idle time
  useEffect(() => {
    if (typeof window !== 'undefined') {
      if ('requestIdleCallback' in window) {
        window.requestIdleCallback(() => preloadModals(), { timeout: 1200 });
      } else {
        setTimeout(preloadModals, 1200);
      }
    }
  }, []);

  // Android hardware back button & popstate overlay navigation
  useEffect(() => {
    window.__mediskyeHandleBack = () => {
      if (isExportOpen) {
        setIsExportOpen(false);
        return true;
      }
      if (memoryOpen) {
        setMemoryOpen(false);
        return true;
      }
      if (isSettingsOpen) {
        setIsSettingsOpen(false);
        return true;
      }
      if (isProfileOpen) {
        setIsProfileOpen(false);
        return true;
      }
      if (selectedSource) {
        setSelectedSource(null);
        return true;
      }
      if (sidebarOpen && (typeof window !== 'undefined' && window.innerWidth < 1024)) {
        setSidebarOpen(false);
        return true;
      }
      return false;
    };

    const handlePopState = (e) => {
      if (window.__mediskyeHandleBack && window.__mediskyeHandleBack()) {
        e.preventDefault?.();
      }
    };
    window.addEventListener('popstate', handlePopState);

    return () => {
      delete window.__mediskyeHandleBack;
      window.removeEventListener('popstate', handlePopState);
    };
  }, [isExportOpen, memoryOpen, isSettingsOpen, isProfileOpen, selectedSource, sidebarOpen]);

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

  // Clean up legacy localStorage chat caches and expired 24h sample report entries on mount
  useEffect(() => {
    try {
      localStorage.removeItem('mediskye_conversations');
      localStorage.removeItem('mediskye_session_id');
      localStorage.removeItem('mediskye_last_active_user');

      // Expire any client-side sample report in localStorage older than 24 hours
      const cutoff = Date.now() - 24 * 60 * 60 * 1000;
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && (key.includes('sample') || key.startsWith('mediskye_sample_'))) {
          try {
            const raw = localStorage.getItem(key);
            const parsed = JSON.parse(raw);
            const ts = parsed?.timestamp || parsed?.created_at ? new Date(parsed.timestamp || parsed.created_at).getTime() : null;
            if (ts && ts < cutoff) {
              localStorage.removeItem(key);
            }
          } catch (_) {}
        }
      }
    } catch (e) {}
  }, []);

  // In-memory conversation state (Neon DB is the single source of truth, hydrated from local cache)
  const [conversations, setConversations] = useState(() => {
    const initPatId = localStorage.getItem('mediskye_patient_id') || 'self';
    const cachedConvs = typeof getCachedConversations === 'function' ? getCachedConversations(initPatId) : null;
    if (Array.isArray(cachedConvs) && cachedConvs.length > 0) {
      return cachedConvs;
    }
    const cachedDocs = typeof getCachedDocuments === 'function' ? getCachedDocuments(initPatId) : null;
    const base = [
      { id: initialSessionId, title: 'New Conversation', messages: [], pdf: null, patient_id: initPatId },
    ];
    if (Array.isArray(cachedDocs) && cachedDocs.length > 0) {
      const docConvs = cachedDocs.map((doc) => ({
        id: doc.id,
        document_id: doc.id,
        title: doc.title || doc.filename || 'Medical Report',
        messages: [],
        pdf: {
          id: doc.id,
          name: doc.filename,
          filename: doc.filename,
          title: doc.title,
          collected_at: doc.collected_at,
          is_future_collection_date: doc.is_future_collection_date,
          size: 8192,
        },
        patient_id: initPatId,
        created_at: doc.created_at,
      }));
      return [...docConvs, ...base];
    }
    return base;
  });

  // Load chat history from backend with race condition protection
  const loadChatHistory = useCallback(async (targetDocId, targetSessionId) => {
    const fetchKey = targetDocId || targetSessionId;
    activeChatFetchRef.current = fetchKey;
    setLoadingHistory(true);
    try {
      const chats = targetDocId
        ? await getDocumentChats(targetDocId)
        : await getDocumentChats(null, targetSessionId);
      // Guard against race conditions if user clicked rapidly between two documents
      if (activeChatFetchRef.current !== fetchKey || (targetSessionId && sessionIdRef.current !== targetSessionId)) {
        return;
      }
      const formatted = Array.isArray(chats)
        ? chats.map((c) => ({
            id: c.id,
            sender: c.role === 'ai' ? 'assistant' : 'user',
            text: c.role === 'ai' ? c.message : (c.message || '').replace(/^["'“”‘’]+|["'“”‘’]+$/g, '').trim(),
            timestamp: c.created_at
              ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : '',
          }))
        : [];

      setConversations((prev) => {
        const next = prev.map((item) => {
          const isTarget = item.id === targetSessionId || (targetDocId && (item.id === targetDocId || item.document_id === targetDocId));
          if (!isTarget) return item;
          if (
            Array.isArray(item.messages) &&
            item.messages.length > 0 &&
            ((!formatted || formatted.length === 0) || item.messages.some((m) => m.isStreaming))
          ) {
            return item;
          }
          return { ...item, messages: formatted };
        });
        try {
          const currentPat = localStorage.getItem('mediskye_patient_id') || 'self';
          if (typeof setCachedConversations === 'function') {
            setCachedConversations(next, currentPat);
          }
        } catch (_) {}
        return next;
      });
    } catch (e) {
      logger.error('Failed to load chat history from backend:', e);
    } finally {
      if (activeChatFetchRef.current === fetchKey) {
        setLoadingHistory(false);
      }
    }
  }, []);

  // Background pre-warmer: pre-downloads full message histories for unvisited sidebar conversations
  const prewarmMessageHistories = useCallback(async (convsToPrewarm, targetPatientId) => {
    if (typeof window === 'undefined' || (typeof navigator !== 'undefined' && !navigator.onLine)) return;
    const patId = targetPatientId || selectedPatientId || 'self';
    const candidateConvs = (convsToPrewarm || [])
      .filter((c) => !c.messages || c.messages.length === 0)
      .slice(0, 15);

    if (candidateConvs.length === 0) return;

    for (const conv of candidateConvs) {
      if (typeof navigator !== 'undefined' && !navigator.onLine) break;
      const targetDocId = conv.document_id || conv.pdf?.id || null;
      const targetSid = conv.sessionId || conv.id;
      try {
        const chats = targetDocId
          ? await getDocumentChats(targetDocId)
          : await getDocumentChats(null, targetSid);

        if (Array.isArray(chats) && chats.length > 0) {
          const formatted = chats.map((c) => ({
            id: c.id,
            sender: c.role === 'ai' ? 'assistant' : 'user',
            text: c.role === 'ai' ? c.message : (c.message || '').replace(/^["'“”‘’]+|["'“”‘’]+$/g, '').trim(),
            timestamp: c.created_at
              ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : '',
          }));
          setConversations((prev) => {
            const next = prev.map((item) => {
              const isTarget = item.id === targetSid || (targetDocId && (item.id === targetDocId || item.document_id === targetDocId));
              if (!isTarget) return item;
              if (item.messages && item.messages.length > 0) return item;
              return { ...item, messages: formatted };
            });
            try {
              if (typeof setCachedConversations === 'function') {
                setCachedConversations(next, patId);
              }
            } catch (_) {}
            return next;
          });
        }
      } catch (_) {}
    }
  }, [selectedPatientId]);

  // Load User, Dependents, and Documents simultaneously on Mount (Bug 10 & Bug 1)
  const refreshPatientContext = useCallback(async (optimisticUser = null) => {
    if (optimisticUser && typeof optimisticUser === 'object' && optimisticUser.id) {
      setCurrentUser(optimisticUser);
      if (optimisticUser.language_preference) {
        setLanguage(optimisticUser.language_preference);
      }
    }
    // Offline fast-path: hydrate cached profile and dependents immediately without waiting for network
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      const cachedUser = typeof getCachedProfile === 'function' ? getCachedProfile() : null;
      const cachedDeps = typeof getCachedDependents === 'function' ? getCachedDependents() : [];
      if (cachedUser) {
        setCurrentUser(cachedUser);
        if (cachedUser.language_preference) {
          setLanguage(cachedUser.language_preference);
        }
      }
      if (Array.isArray(cachedDeps) && cachedDeps.length > 0) {
        setDependents(cachedDeps);
      }
      return;
    }
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

  // Reusable document refresher: synchronizes server document & conversation truth with local state
  const refreshDocuments = useCallback(async (activeDocId = null, overrideTitle = null, targetPatientId = null) => {
    const activePatId = targetPatientId || selectedPatientId || (typeof localStorage !== 'undefined' ? localStorage.getItem('mediskye_patient_id') : null) || 'self';

    // Offline fast-path: hydrate from cache immediately and return early without overwriting with empty network responses
    if (typeof navigator !== 'undefined' && !navigator.onLine) {
      const cachedDocs = typeof getCachedDocuments === 'function' ? getCachedDocuments(activePatId) : [];
      const cachedConvs = typeof getCachedConversations === 'function' ? getCachedConversations(activePatId) : null;
      if (Array.isArray(cachedConvs) && cachedConvs.length > 0) {
        setConversations(cachedConvs);
        const firstDocConv = cachedConvs.find((c) => c.pdf || c.document_id);
        if (firstDocConv?.pdf) {
          setActivePdf(firstDocConv.pdf);
        }
      } else if (Array.isArray(cachedDocs) && cachedDocs.length > 0) {
        const docConvs = cachedDocs.map((doc) => ({
          id: doc.id,
          document_id: doc.id,
          title: doc.title || doc.filename || 'Medical Report',
          messages: [],
          pdf: {
            id: doc.id,
            name: doc.filename,
            filename: doc.filename,
            title: doc.title,
            collected_at: doc.collected_at,
            is_future_collection_date: doc.is_future_collection_date,
            size: 8192,
          },
          patient_id: doc.dependent_id || activePatId,
          created_at: doc.created_at,
        }));
        setConversations(docConvs);
        if (docConvs[0]?.pdf) {
          setActivePdf(docConvs[0].pdf);
        }
      }
      return Array.isArray(cachedDocs) ? cachedDocs : [];
    }

    try {
      const [docsRes, generalChatsRes] = await Promise.all([
        getUserDocuments(activePatId).catch(() => []),
        getGeneralChats().catch(() => []),
      ]);
      const docs = Array.isArray(docsRes) ? docsRes : [];
      let effectiveDocs = [...docs];
      if (typeof setCachedDocuments === 'function') {
        setCachedDocuments(effectiveDocs, activePatId);
      }

      // Group standalone chats by session_id
      const generalChats = Array.isArray(generalChatsRes) ? generalChatsRes : [];
      const standaloneChatsBySession = new Map();
      generalChats.forEach((c) => {
        if (!c.document_id) {
          const sid = c.session_id || 'legacy-standalone';
          if (!standaloneChatsBySession.has(sid)) {
            standaloneChatsBySession.set(sid, []);
          }
          standaloneChatsBySession.get(sid).push(c);
        }
      });

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

        const existingMap = new Map();
        prev.forEach((c) => {
          if (c.id) existingMap.set(c.id, c);
          if (c.document_id) existingMap.set(c.document_id, c);
        });

        // 1. Reconstruct document-bound conversations
        const syncedDocConvs = effectiveDocs.map((doc) => {
          const existing = existingMap.get(doc.id);
          const pdfMeta = {
            id: doc.id,
            name: doc.filename,
            filename: doc.filename,
            title: doc.title,
            collected_at: doc.collected_at,
            is_future_collection_date: doc.is_future_collection_date,
            size: 8192,
          };
          const resolvedDocTitle = (activeDocId && doc.id === activeDocId && overrideTitle)
            ? overrideTitle
            : doc.title;

          let messages = (existing?.messages && existing.messages.length > 0)
            ? existing.messages
            : [];

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
              collected_at: doc.collected_at || existing?.collected_at,
              is_future_collection_date: doc.is_future_collection_date,
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
            collected_at: doc.collected_at,
            is_future_collection_date: doc.is_future_collection_date,
          };
        });

        // 2. Reconstruct standalone conversations from server session_id grouping
        const serverStandaloneConvs = [];
        standaloneChatsBySession.forEach((messagesList, sid) => {
          const existing = existingMap.get(sid);
          const title = existing?.title && existing.title !== 'New Conversation'
            ? existing.title
            : (messagesList[0]?.session_title || 'New Conversation');

          const formattedMessages = messagesList.map((c) => ({
            id: c.id,
            sender: c.role === 'ai' ? 'assistant' : 'user',
            text: c.role === 'ai' ? c.message : (c.message || '').replace(/^["'“”‘’]+|["'“”‘’]+$/g, '').trim(),
            timestamp: c.created_at
              ? new Date(c.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
              : '',
          }));

          serverStandaloneConvs.push({
            id: sid,
            document_id: null,
            patient_id: messagesList[0]?.dependent_id || existing?.patient_id || 'self',
            title,
            messages: (existing?.messages && existing.messages.length > formattedMessages.length)
              ? existing.messages
              : (formattedMessages.length > 0 ? formattedMessages : (existing?.messages || [])),
            pdf: null,
            created_at: messagesList[0]?.created_at || null,
          });
        });

        // 3. Retain local non-document conversations with messages if not yet on server
        const localNonDocConvs = prev.filter(
          (c) => !c.document_id && !c.pdf && !effectiveDocs.some((d) => d.id === c.id) && !standaloneChatsBySession.has(c.id)
        );

        const allConvs = [...syncedDocConvs, ...serverStandaloneConvs, ...localNonDocConvs];
        const finalConvs =
          allConvs.length === 0
            ? [{ id: sessionIdRef.current, title: 'New Conversation', messages: [], pdf: null, patient_id: 'self' }]
            : allConvs;

        try {
          if (typeof setCachedConversations === 'function') {
            setCachedConversations(finalConvs, activePatId);
          }
        } catch (_) {}

        if (typeof navigator !== 'undefined' && navigator.onLine) {
          setTimeout(() => {
            prewarmMessageHistories(finalConvs, activePatId);
          }, 50);
        }

        return finalConvs;
      });

      return docs;
    } catch (err) {
      logger.error('Failed to refresh documents:', err);
      return [];
    }
  }, [selectedPatientId]);

  // Synchronize with server truth on account load / refresh (Neon DB single source of truth)
  useEffect(() => {
    if (currentUser?.id) {
      if (userLoadedRef.current === currentUser.id) return;
      userLoadedRef.current = currentUser.id;

      refreshDocuments().then((docs) => {
        if (docs && docs.length > 0) {
          const targetDoc = docs[0];
          const pdfMeta = {
            id: targetDoc.id,
            name: targetDoc.filename,
            filename: targetDoc.filename,
            title: targetDoc.title,
            collected_at: targetDoc.collected_at,
            is_future_collection_date: targetDoc.is_future_collection_date,
            size: 8192,
          };
          setActivePdf(pdfMeta);
          setSessionId(targetDoc.id);
          if (targetDoc.patient_id) {
            setSelectedPatientId(targetDoc.patient_id);
          }
          loadChatHistory(targetDoc.id, targetDoc.id);
        } else {
          setActivePdf(null);
          loadChatHistory(null, sessionIdRef.current);
        }
        // Pre-warm local cache for active patient in background
        const activePat = localStorage.getItem('mediskye_patient_id') || 'self';
        prewarmPatientLocalCache(activePat, dependents || [], docs || []);
      }).catch(() => {
        setActivePdf(null);
      });
    }
  }, [currentUser, refreshDocuments, loadChatHistory, dependents]);

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

  const handlePatientSelect = async (patientId) => {
    abortControllerRef.current?.abort();
    abortControllerRef.current = null;
    stopSpeaking();
    setIsGenerating(false);
    isSubmittingRef.current = false;
    const targetPatientId = patientId || 'self';
    setSelectedPatientId(targetPatientId);
    localStorage.setItem('mediskye_patient_id', targetPatientId);
    setViewMode('chat');
    setIsProfileOpen(false);

    // Pre-warm local cache for target profile in background
    setTimeout(() => {
      prewarmPatientLocalCache(targetPatientId, dependents || []);
    }, 50);

    // Hard profile lock: never auto-reassign staged documents or conversations across patients
    const currentPatient = currentChat.patient_id || 'self';

    if (currentPatient !== targetPatientId) {
      // Find candidate conversation for target profile
      const candidate = conversations.find(
        (c) => (c.patient_id || 'self') === targetPatientId && c.id !== sessionId
      );
      if (candidate) {
        setSessionId(candidate.id);
        sessionIdRef.current = candidate.id;
        setActivePdf(candidate.pdf || null);
        loadChatHistory(candidate.document_id || null, candidate.id);
        return;
      }

      // Hydrate cached conversations for target patient if available
      const cachedTargetConvs = getCachedConversations(targetPatientId);
      if (Array.isArray(cachedTargetConvs) && cachedTargetConvs.length > 0) {
        const firstTargetChat = cachedTargetConvs[0];
        if (firstTargetChat) {
          setSessionId(firstTargetChat.id);
          sessionIdRef.current = firstTargetChat.id;
          setActivePdf(firstTargetChat.pdf || null);
          loadChatHistory(firstTargetChat.document_id || null, firstTargetChat.id);
          return;
        }
      }

      // Switch to a fresh empty consultation for the newly selected profile
      const newId = generateSessionId();
      setSessionId(newId);
      sessionIdRef.current = newId;
      setActivePdf(null);
      setConversations((prev) => {
        const cleaned = prev.filter(
          (c) => (c.messages && c.messages.length > 0) || c.pdf || c.document_id
        );
        return [
          { id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: targetPatientId },
          ...cleaned,
        ];
      });
      return;
    }

    if (!currentChat.pdf && !currentChat.document_id && (!currentChat.messages || currentChat.messages.length === 0)) {
      setConversations((prev) =>
        prev.map((c) => (c.id === sessionId ? { ...c, patient_id: targetPatientId } : c))
      );
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
      setUploadError('Invalid file type or size.');
      return null;
    }

    const maxMb = 50;
    if (file.size > maxMb * 1024 * 1024) {
      console.error(`File Too Large: Maximum allowed file size is ${maxMb}MB.`);
      setUploadError('Invalid file type or size.');
      return null;
    }

    setUploadError(null);
    setIsGenerating(true);
    clearUploadTimers();
    const uploadStartedAt = Date.now();
    setUploadState({ phase: 'uploading', fileName: file.name, startedAt: uploadStartedAt, warming: false });

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
              setUploadState((prev) => ({ ...(prev || {}), phase: 'error', finishedAt: Date.now(), error: 'We lost contact with the processing service. If the report finishes, it will appear in your history.' }));
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
          {
            // Prefer an explicit backend stage when present; otherwise infer from poll cadence.
            const stage = String(status.stage || status.phase || '').toLowerCase();
            let phase = pollIndex <= 1 ? 'extracting' : 'indexing';
            if (/extract|ocr|pars|text/.test(stage)) phase = 'extracting';
            else if (/index|embed|faiss|bm25|vector/.test(stage) || status.index_status) phase = 'indexing';
            else if (/valid|queue|pending/.test(stage)) phase = 'uploading';
            setUploadState((prev) => (prev ? { ...prev, phase } : prev));
          }
        }

        if (!newDocId) {
          setUploadState((prev) => ({ ...(prev || {}), phase: 'error', finishedAt: Date.now(), error: 'This report is taking longer than expected. It will appear in your history as soon as processing finishes.' }));
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
      // Step A complete → ready for Q&A; Step B (summary/metrics cache warming) continues server-side.
      setUploadState((prev) => ({ ...(prev || { fileName: file.name, startedAt: uploadStartedAt }), phase: 'ready', finishedAt: Date.now(), warming: true }));
      uploadTimersRef.current.push(
        setTimeout(() => setUploadState((prev) => (prev && prev.phase === 'ready' ? { ...prev, warming: false } : prev)), 6000),
        setTimeout(() => setUploadState((prev) => (prev && prev.phase === 'ready' ? null : prev)), 9000)
      );
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
      const errMsg = err?.response?.data?.detail || err?.message || 'Upload failed. Please try again.';
      setUploadError(errMsg);
      setUploadState((prev) => ({ ...(prev || { fileName: file.name }), phase: 'error', finishedAt: Date.now(), error: errMsg }));
      setActivePdf(null);
      return null;
    } finally {
      setUploadProgress(null);
      setIsGenerating(false);
    }
  };

  const handleDetachDocument = (docId) => {
    try {
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
    const cleanUserQuery = (userQuery || '').replace(/^["'“”‘’]+|["'“”‘’]+$/g, '').trim();
    if (!cleanUserQuery || isSubmittingRef.current || isGenerating) return;
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
      text: cleanUserQuery,
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

        if (typeof chunk.replace === 'string') {
          assistantAccum = chunk.replace;
        } else if (chunk.chunk || chunk.token) {
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
            if (typeof chunk.replace === 'string') {
              targetMsg.text = chunk.replace;
              targetMsg.status = null;
            } else if (chunk.stage && chunk.message) {
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
          const next = prev.map((c) => {
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
          try {
            const currentPat = localStorage.getItem('mediskye_patient_id') || 'self';
            if (typeof setCachedConversations === 'function') {
              setCachedConversations(next, currentPat);
            }
          } catch (_) {}
          return next;
        });
      }
      if (abortControllerRef.current === controller) {
        abortControllerRef.current = null;
        setIsGenerating(false);
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

    // If current conversation already has 0 messages and no active PDF, don't create duplicate
    const activeChat = conversations.find((c) => c.id === sessionId);
    if (activeChat && (!activeChat.messages || activeChat.messages.length === 0) && !activePdf) {
      return;
    }

    const newId = generateSessionId();
    setSessionId(newId);
    setActivePdf(null);
    setViewMode('chat');
    setIsProfileOpen(false);
    setConversations((prev) => {
      // Omit empty 0-message sessions from history
      const cleaned = prev.filter(
        (c) => (c.messages && c.messages.length > 0) || c.pdf || c.document_id
      );
      return [
        { id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId },
        ...cleaned,
      ];
    });
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

    // Clean up empty 0-message conversations when switching away
    setConversations((prev) =>
      prev.filter((c) => c.id === id || (c.messages && c.messages.length > 0) || c.pdf || c.document_id)
    );

    setSessionId(id);
    setViewMode('chat');
    const chat = conversations.find((c) => c.id === id);
    if (chat) {
      setActivePdf(chat.pdf || null);
      const pId = chat.patient_id || 'self';
      setSelectedPatientId(pId);
      localStorage.setItem('mediskye_patient_id', pId);
      const targetDocId = chat.document_id || (chat.pdf ? id : null);
      await loadChatHistory(targetDocId, id);
    } else {
      setSelectedPatientId('self');
      localStorage.setItem('mediskye_patient_id', 'self');
      await loadChatHistory(null, id);
    }
    setIsProfileOpen(false);
  };

  const handleClearAllChats = async () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopSpeaking();
    setIsGenerating(false);
    isSubmittingRef.current = false;

    try {
      await clearAllChatSessions(null, true);
    } catch (e) {
      logger.warn('Failed clearing chats on backend:', e);
    }

    const newId = generateSessionId();
    setSessionId(newId);
    setActivePdf(null);
    setConversations([{ id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId }]);
    setPdfs([]);
    setLabMetrics([]);

    try {
      const keys = Object.keys(localStorage);
      for (const k of keys) {
        if (
          k.startsWith('mediskye_conversation') ||
          k.startsWith('mediskye_chat') ||
          k.startsWith('mediskye_session') ||
          k.startsWith('mediskye_pdf') ||
          k.startsWith('mediskye_active_pdf')
        ) {
          localStorage.removeItem(k);
        }
      }
      localStorage.removeItem('mediskye_conversations');
      localStorage.removeItem('mediskye_session_id');
      if (currentUser?.id) {
        localStorage.removeItem(`mediskye_conversations_${currentUser.id}`);
      }
    } catch (_) {}

    await refreshDocuments();

    try {
      const freshUser = await getProfile();
      if (freshUser) {
        setCurrentUser(freshUser);
      }
    } catch (profErr) {
      logger.warn('Failed to refresh profile after clearing chats:', profErr);
    }

    setIsSettingsOpen(false);
  };

  const handleResetProfileChats = async (targetProfileId = 'self') => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    stopSpeaking();
    setIsGenerating(false);
    isSubmittingRef.current = false;

    try {
      await clearAllChatSessions(targetProfileId, false);
    } catch (e) {
      logger.warn('Failed resetting profile chats on backend:', e);
    }

    try {
      const keys = Object.keys(localStorage);
      for (const k of keys) {
        if (
          k.startsWith('mediskye_conversation') ||
          k.startsWith('mediskye_chat') ||
          k.startsWith('mediskye_session') ||
          k.startsWith('mediskye_pdf')
        ) {
          if (targetProfileId === 'self' || targetProfileId === null) {
            localStorage.removeItem(k);
          } else if (k.includes(String(targetProfileId))) {
            localStorage.removeItem(k);
          }
        }
      }
      if (targetProfileId === 'self') {
        localStorage.removeItem('mediskye_conversations');
        localStorage.removeItem('mediskye_session_id');
      }
    } catch (_) {}

    if (targetProfileId === selectedPatientId || (targetProfileId === 'self' && isSelfSelected(selectedPatientId))) {
      const newId = generateSessionId();
      setSessionId(newId);
      setActivePdf(null);
      setConversations([{ id: newId, title: 'New Conversation', messages: [], pdf: null, patient_id: selectedPatientId }]);
    } else {
      setConversations((prev) => prev.filter((c) => c.dependent_id !== targetProfileId && c.patient_id !== targetProfileId));
    }

    await refreshDocuments();
    await refreshPatientContext();
    setIsSettingsOpen(false);
  };

  const handleDependentDeleted = useCallback(async (deletedDepId) => {
    if (selectedPatientId === deletedDepId) {
      setSelectedPatientId('self');
      try {
        localStorage.setItem('mediskye_patient_id', 'self');
      } catch (_) {}
    }
    try {
      const keys = Object.keys(localStorage);
      for (const k of keys) {
        if (k.includes(String(deletedDepId))) {
          localStorage.removeItem(k);
        }
      }
    } catch (_) {}
    setConversations((prev) => prev.filter((c) => c.dependent_id !== deletedDepId && c.patient_id !== deletedDepId));
    setPdfs((prev) => prev.filter((p) => p.dependent_id !== deletedDepId));
    await refreshPatientContext();
    await refreshDocuments();
  }, [selectedPatientId, refreshPatientContext, refreshDocuments]);

  const handleDeleteChat = async (id, skipConfirm = false) => {
    const chat = conversations.find((c) => c.id === id);
    const targetDocId = chat?.document_id || (chat?.pdf ? id : null);

    // 0ms Optimistic UI update: immediately remove from state and advance active session
    setConversations((prev) => {
      const newConversations = prev.filter((c) => c.id !== id && (!targetDocId || c.document_id !== targetDocId));
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

    try {
      if (targetDocId) {
        await deleteDocument(targetDocId);
      } else {
        await deleteChatSession(id, selectedPatientId);
      }
      refreshDocuments().catch(() => {});
    } catch (err) {
      logger.error('Delete failed:', err);
      refreshDocuments().catch(() => {});
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
      try {
        const res = await renameChatSession(id, trimmed);
        const savedTitle = res?.title || trimmed;
        setConversations((prev) =>
          prev.map((c) => (c.id === id ? { ...c, title: savedTitle } : c))
        );
      } catch (err) {
        logger.error('Failed to rename chat session:', err);
        setConversations((prev) =>
          prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c))
        );
      }
    }
  };

  // Theme is locked to dark; kept as a no-op for child component prop contracts.
  const handleSetDarkMode = useCallback(() => {}, []);

  const handleDeleteAccount = async () => {
    try {
      await deleteAccount();
      invalidateMetrics();
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

  // ══════════════════════════════════════════════════════════════════════
  //  Workbench state (presentation layer — no backend contract changes)
  // ══════════════════════════════════════════════════════════════════════
  const { i18n } = useTranslation();
  const viewport = useViewport();
  const { isDesktop, isMobile } = viewport;

  const [inspectorOpen, setInspectorOpen] = useState(() => {
    const stored = readStorage(STORAGE_KEYS.inspectorOpen, null);
    if (stored !== null) return stored === 'true';
    // Wide screens open the split view by default; narrower desktops opt in.
    return typeof window !== 'undefined' && window.innerWidth >= 1280;
  });
  const [inspectorTab, setInspectorTabState] = useState(() => {
    const stored = readStorage(STORAGE_KEYS.inspectorTab, 'overview');
    return ['overview', 'metrics', 'trends', 'report'].includes(stored) ? stored : 'overview';
  });
  const [metricsFilter, setMetricsFilter] = useState('all');
  const [metricsSearch, setMetricsSearch] = useState('');
  const [highlightKey, setHighlightKey] = useState(null);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [printSignal, setPrintSignal] = useState(0);
  const uiLanguage = (i18n?.language || 'en').startsWith('hi') ? 'hi' : 'en';

  const setInspectorTab = useCallback((tab) => {
    setInspectorTabState(tab);
    writeStorage(STORAGE_KEYS.inspectorTab, tab);
  }, []);

  const handleToggleInspector = useCallback(
    (tab = null, force = undefined) => {
      if (!isDesktop) {
        // On phones/tablets the inspector is a full-screen view
        if (force === false) {
          setViewMode('chat');
          return;
        }
        if (tab) setInspectorTab(tab);
        setViewMode(tab === 'overview' || tab === 'trends' ? 'analytics' : 'metrics');
        return;
      }
      let next;
      if (force !== undefined) next = force;
      else if (inspectorOpen && tab && tab !== inspectorTab) next = true;
      else next = !inspectorOpen;
      setInspectorOpen(next);
      writeStorage(STORAGE_KEYS.inspectorOpen, next);
      // Below 1280px three columns don't fit: fold the history into the rail
      // (transient — the persisted sidebar preference is untouched).
      if (next && !inspectorOpen && sidebarOpen && typeof window !== 'undefined' && window.innerWidth < 1280) {
        setSidebarOpen(false);
      }
      if (tab) setInspectorTab(tab);
    },
    [isDesktop, inspectorOpen, inspectorTab, setInspectorTab, sidebarOpen]
  );

  const activeDocId = currentChat.document_id || activePdf?.id || null;
  const inspectorVisible = isDesktop && inspectorOpen && Boolean(activePdf);
  const analyticsVisible = !isDesktop && Boolean(activePdf) && viewMode !== 'chat';

  const labMetrics = useLabMetrics(activeDocId, {
    enabled: Boolean(activeDocId) && (inspectorVisible || analyticsVisible || paletteOpen),
  });

  // Reset metric focus when switching reports
  useEffect(() => {
    setHighlightKey(null);
    setMetricsSearch('');
    setMetricsFilter('all');
  }, [activeDocId]);

  // Patient-scoped report list feeds the longitudinal trend builder
  const patientReports = useMemo(() => {
    const target = isSelfSelected(selectedPatientId, currentUser) ? 'self' : String(selectedPatientId);
    return conversations
      .filter((c) => c.document_id || c.pdf)
      .filter((c) => String(c.patient_id || 'self') === target)
      .map((c) => ({
        id: c.document_id || c.id,
        title: c.title,
        filename: c.pdf?.filename || c.pdf?.name,
        collected_at: c.collected_at || c.pdf?.collected_at,
        created_at: c.created_at,
      }));
  }, [conversations, selectedPatientId, currentUser]);

  const trends = useTrendData({
    patientId: selectedPatientId,
    reports: patientReports,
    enabled: Boolean(activeDocId) && inspectorTab === 'trends' && (inspectorVisible || analyticsVisible),
  });

  const patientFilteredConversations = useMemo(() => {
    const isSelf = isSelfSelected(selectedPatientId, currentUser);
    return (conversations || []).filter((c) => {
      const chatPat = c.patient_id;
      if (isSelf) {
        return !chatPat || chatPat === 'self' || (currentUser && String(chatPat) === String(currentUser.id));
      }
      return String(chatPat) === String(selectedPatientId);
    });
  }, [conversations, selectedPatientId, currentUser]);

  const isProfileLocked = Boolean(
    activePdf ||
    currentChat?.pdf ||
    currentChat?.document_id ||
    (currentChat?.messages && currentChat.messages.length > 0)
  );

  const handleLockedProfileClick = useCallback(() => {
    setSyncToast('Profile is locked for this report chat. Start a New Chat to switch profiles.');
    setTimeout(() => setSyncToast(null), 3000);
  }, []);

  const handleManualCloudSync = useCallback(async () => {
    if (isSyncing) return;
    setIsSyncing(true);
    try {
      const patId = selectedPatientId || 'self';
      // 1. Fetch fresh profile & dependents and update React state + local cache
      const [freshProfile, freshDeps] = await Promise.all([
        getProfile().catch(() => null),
        getDependents().catch(() => null),
      ]);
      if (freshProfile) {
        setCurrentUser(freshProfile);
        setCachedProfile(currentUser?.id || freshProfile.id, freshProfile);
      }
      if (Array.isArray(freshDeps)) {
        setDependents(freshDeps);
        setCachedDependents(currentUser?.id || freshProfile?.id, freshDeps);
      }

      // 2. Refresh documents & chats from Neon DB
      await refreshDocuments();

      // 3. Update active conversation's messages in place if attached
      const targetDocId = activePdf?.id || currentChat?.document_id || null;
      const targetSid = sessionId || currentChat?.id || null;
      if (targetDocId) {
        await loadChatHistory(targetDocId, targetSid);
      } else if (targetSid) {
        await loadChatHistory(null, targetSid);
      }

      // 4. Re-fetch memory facts, patient trends, and lab metrics
      await Promise.all([
        getMemoryFacts(patId).catch(() => []),
        getMetricTrends(patId).catch(() => ({})),
        targetDocId && labMetrics?.reload ? labMetrics.reload().catch(() => null) : Promise.resolve(null),
      ]);

      // 5. Pre-warm unvisited message histories for offline reading
      setTimeout(() => {
        prewarmMessageHistories(conversations, patId);
      }, 50);

      setSyncToast('Synced with cloud');
      setTimeout(() => setSyncToast(null), 2000);
    } catch (err) {
      logger.warn('Manual cloud sync failed:', err);
    } finally {
      setIsSyncing(false);
    }
  }, [isSyncing, currentUser, activePdf, currentChat, sessionId, selectedPatientId, refreshDocuments, loadChatHistory, labMetrics, prewarmMessageHistories, conversations]);

  handleManualCloudSyncRef.current = handleManualCloudSync;

  const reportCounts = useMemo(() => {
    const counts = {};
    conversations.forEach((c) => {
      if (!(c.document_id || c.pdf)) return;
      const k = String(c.patient_id || 'self');
      counts[k] = (counts[k] || 0) + 1;
    });
    if (currentUser?.id && counts[String(currentUser.id)]) {
      counts.self = (counts.self || 0) + counts[String(currentUser.id)];
    }
    return counts;
  }, [conversations, currentUser]);

  const activePatient = useMemo(() => {
    if (isSelfSelected(selectedPatientId, currentUser)) return currentUser;
    return dependents?.find((d) => String(d.id) === String(selectedPatientId)) || currentUser;
  }, [selectedPatientId, currentUser, dependents]);

  const patientName = useMemo(() => {
    if (isSelfSelected(selectedPatientId, currentUser)) return currentUser?.full_name || null;
    const dep = (dependents || []).find((x) => String(x.id) === String(selectedPatientId));
    return dep?.full_name || null;
  }, [currentUser, dependents, selectedPatientId]);

  const handleFocusMetric = useCallback(
    (row) => {
      const key = metricKey(row);
      setHighlightKey(key);
      setMetricsFilter('all');
      setMetricsSearch(metricName(row));
      handleToggleInspector('metrics', true);
    },
    [handleToggleInspector]
  );

  const handleAskAbout = (row) => {
    const name = metricName(row);
    const prev = row.previous_value ? ` It was ${row.previous_value} previously.` : '';
    const q = `Explain my ${name} result of ${row.value}${row.unit ? ` ${row.unit}` : ''} (reference ${row.range || row.reference_range || 'not stated'}).${prev} What does it mean and what should I ask my doctor?`;
    if (!isDesktop) setViewMode('chat');
    handleSendMessage(q);
  };

  const handleSetUiLanguage = (lang) => {
    try {
      i18n?.changeLanguage?.(lang);
      localStorage.setItem(STORAGE_KEYS.uiLang, lang);
    } catch (e) {
      logger.warn('Failed to switch UI language:', e);
    }
  };

  const openUpload = () => chatInputRef.current?.openFileUpload();
  const requestPrint = () => {
    if (activePdf) setPrintSignal((n) => n + 1);
  };

  useHotkeys([
    { combo: 'mod+k', handler: () => setPaletteOpen((o) => !o), allowInInput: true },
    { combo: 'mod+b', handler: toggleSidebar, allowInInput: true },
    { combo: 'mod+\\', handler: () => handleToggleInspector(), allowInInput: true, enabled: Boolean(activePdf) },
    { combo: 'mod+u', handler: openUpload, allowInInput: true },
    { combo: 'mod+shift+o', handler: handleNewChat, allowInInput: true },
    { combo: 'mod+shift+p', handler: requestPrint, allowInInput: true, enabled: Boolean(activePdf) },
    { combo: 'mod+shift+m', handler: () => setMemoryOpen(true), allowInInput: true },
    { combo: 'mod+,', handler: () => setIsSettingsOpen(true), allowInInput: true },
    { combo: 'alt+1', handler: () => handleToggleInspector('overview', true), enabled: Boolean(activePdf) },
    { combo: 'alt+2', handler: () => handleToggleInspector('metrics', true), enabled: Boolean(activePdf) },
    { combo: 'alt+3', handler: () => handleToggleInspector('trends', true), enabled: Boolean(activePdf) },
    { combo: 'alt+4', handler: () => handleToggleInspector('report', true), enabled: Boolean(activePdf) },
    { combo: '/', handler: () => chatInputRef.current?.focus?.() },
  ]);

  const attachedDocuments =
    Array.isArray(currentChat.documents) && currentChat.documents.length > 0
      ? currentChat.documents
      : activePdf
        ? [{ id: currentChat.document_id || 'doc-1', name: activePdf.name, filename: activePdf.name }]
        : [];

  const composerDocuments =
    Array.isArray(currentChat.documents) && currentChat.documents.length > 1
      ? currentChat.documents
      : messages.length === 0 && activePdf
        ? [{ id: currentChat.document_id || activePdf.id || 'doc-1', name: activePdf.name, filename: activePdf.name }]
        : [];

  const sidebarPushes = isDesktop && sidebarOpen;

  return (
    <div className="relative flex h-app w-screen overflow-hidden bg-obsidian text-ink">
      {/* Drawer backdrop on tablet / phone */}
      {sidebarOpen && !isDesktop && (
        <div
          data-testid="sidebar-backdrop"
          className="fixed inset-0 bg-black/60 backdrop-blur-[2px] z-30 lg:hidden animate-backdrop-in"
          onClick={toggleSidebar}
        />
      )}

      <div
        data-testid="sidebar-wrapper"
        className={`fixed inset-y-0 left-0 z-40 w-[min(300px,86vw)] lg:w-[272px] flex-shrink-0 transition-transform ${
          sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
        style={{
          transitionDuration: '220ms',
          transitionTimingFunction: 'cubic-bezier(0.16, 1, 0.3, 1)',
          transform: sidebarOpen ? 'translate3d(0, 0, 0)' : 'translate3d(-100%, 0, 0)',
          willChange: 'transform',
        }}
        aria-hidden={!sidebarOpen}
      >
        <Sidebar
          isOpen={sidebarOpen}
          onToggle={toggleSidebar}
          conversations={patientFilteredConversations}
          activeSessionId={sessionId}
          onSelectChat={(id) => {
            closeSidebarOnSmallScreens();
            return handleSelectChat(id);
          }}
          onDeleteChat={handleDeleteChat}
          onRenameChat={handleRenameChat}
          onNewChat={() => {
            closeSidebarOnSmallScreens();
            handleNewChat();
          }}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onOpenProfile={handleOpenProfile}
          onOpenMemory={() => setMemoryOpen(true)}
          onOpenPalette={() => setPaletteOpen(true)}
          darkMode={darkMode}
          setDarkMode={handleSetDarkMode}
          activePdf={activePdf}
          language={language}
          setLanguage={setLanguage}
          onLogout={handleLogout}
          currentUser={currentUser}
          dependents={dependents}
        />
      </div>

      {isDesktop && !sidebarOpen && (
        <NavRail
          onExpand={toggleSidebar}
          onNewChat={handleNewChat}
          onOpenPalette={() => setPaletteOpen(true)}
          onUpload={openUpload}
          onOpenMemory={() => setMemoryOpen(true)}
          onOpenCaregivers={handleOpenDependents}
          onOpenSettings={() => setIsSettingsOpen(true)}
          currentUser={currentUser}
        />
      )}

      <main
        className={cn(
          'flex-1 min-w-0 flex flex-col h-full overflow-hidden relative bg-ambient transition-[margin] ease-out',
          sidebarPushes ? 'lg:ml-[272px]' : isDesktop ? 'lg:ml-14' : 'ml-0'
        )}
        style={{ transitionDuration: '260ms' }}
      >
        <Workbench
          isDesktop={isDesktop}
          isMobile={isMobile}
          toggleSidebar={toggleSidebar}
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          onSelectPatient={handlePatientSelect}
          onOpenDependents={handleOpenDependents}
          isProfileLocked={isProfileLocked}
          onLockedProfileClick={handleLockedProfileClick}
          activePatient={activePatient}
          patientName={patientName}
          reportCounts={reportCounts}
          messages={messages}
          isGenerating={isGenerating}
          loadingHistory={loadingHistory}
          onRegenerate={handleRegenerate}
          onSendMessage={handleSendMessage}
          onTrySampleReport={handleSampleReportClick}
          onAttachFile={handleAttachFile}
          onStopGeneration={handleStopGeneration}
          chatInputRef={chatInputRef}
          composerDocuments={composerDocuments}
          onDetachDocument={handleDetachDocument}
          onRemoveFile={handleRemoveFile}
          activePdf={activePdf}
          documentId={currentChat.document_id}
          attachedDocuments={attachedDocuments}
          metrics={labMetrics.metrics}
          metricsLoading={labMetrics.loading}
          metricsError={labMetrics.error}
          onReloadMetrics={labMetrics.reload}
          ensureMetrics={labMetrics.ensure}
          trends={trends}
          inspectorOpen={inspectorOpen}
          onToggleInspector={handleToggleInspector}
          inspectorTab={inspectorTab}
          onInspectorTabChange={setInspectorTab}
          metricsFilter={metricsFilter}
          onMetricsFilterChange={setMetricsFilter}
          metricsSearch={metricsSearch}
          onMetricsSearchChange={(v) => {
            setMetricsSearch(v);
            if (!v) setHighlightKey(null);
          }}
          highlightKey={highlightKey}
          onFocusMetric={handleFocusMetric}
          onAskAbout={handleAskAbout}
          viewMode={viewMode}
          onViewModeChange={setViewMode}
          uploadState={uploadState}
          onDismissUpload={() => {
            clearUploadTimers();
            setUploadState(null);
          }}
          uploadError={uploadError}
          onDismissUploadError={() => setUploadError(null)}
          isExportingSummary={isExportingSummary}
          printSummaryText={printSummaryText}
          onExportSummary={handleExportSummary}
          onOpenExport={() => setIsExportOpen(true)}
          onOpenPalette={() => setPaletteOpen(true)}
          onOpenSettings={() => setIsSettingsOpen(true)}
          onOpenMemory={() => setMemoryOpen(true)}
          onOpenProfile={handleOpenProfile}
          uiLanguage={uiLanguage}
          onSetUiLanguage={handleSetUiLanguage}
          printSignal={printSignal}
          isOnline={isOnline}
          onManualSync={handleManualCloudSync}
          isSyncing={isSyncing}
        />
        {syncToast && (
          <div className="fixed top-16 right-6 z-50 flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-slate-900/95 border border-cyan-500/40 text-cyan-300 text-xs shadow-xl animate-fade-in backdrop-blur-md">
            <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
            <span>{syncToast}</span>
          </div>
        )}
      </main>

      {paletteOpen && (
        <CommandPalette
          open={paletteOpen}
          onOpenChange={setPaletteOpen}
          conversations={patientFilteredConversations}
          activeSessionId={sessionId}
          metrics={labMetrics.metrics}
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          uiLanguage={uiLanguage}
          hasActiveReport={Boolean(activePdf)}
          actions={{
            ask: (q) => {
              if (!isDesktop) setViewMode('chat');
              handleSendMessage(q);
            },
            newChat: handleNewChat,
            upload: openUpload,
            printSummary: requestPrint,
            exportChat: () => setIsExportOpen(true),
            openInspector: (tab) => handleToggleInspector(tab, true),
            toggleInspector: isDesktop && activePdf ? () => handleToggleInspector() : null,
            toggleSidebar,
            openMemory: () => setMemoryOpen(true),
            openCaregivers: handleOpenDependents,
            openSettings: () => setIsSettingsOpen(true),
            setUiLanguage: handleSetUiLanguage,
            selectPatient: handlePatientSelect,
            selectChat: handleSelectChat,
            focusMetric: handleFocusMetric,
            logout: handleLogout,
          }}
        />
      )}

      <Suspense fallback={null}>
        <MemoryVault
          open={memoryOpen}
          onOpenChange={setMemoryOpen}
          selectedPatientId={selectedPatientId}
          activePatientId={selectedPatientId}
          patientName={patientName}
          currentUser={currentUser}
          dependents={dependents}
          documents={patientReports}
          onConsentChanged={(next) => setCurrentUser((u) => (u ? { ...u, memory_consent_granted: next } : u))}
        />

        <DocumentModal source={selectedSource} onClose={() => setSelectedSource(null)} />

        <ExportModal
          isOpen={isExportOpen}
          onClose={() => setIsExportOpen(false)}
          darkMode={darkMode}
          documentId={currentChat.document_id || null}
          documentTitle={currentChat.title || (activePdf ? activePdf.name : null)}
          messages={messages}
          user={activePatient}
        />

        <SettingsModal
          isOpen={isSettingsOpen}
          onClose={() => setIsSettingsOpen(false)}
          darkMode={darkMode}
          setDarkMode={handleSetDarkMode}
          themePreference={themePreference}
          setThemePreference={setThemePreference}
          onClearAllChats={handleClearAllChats}
          onResetProfileChats={handleResetProfileChats}
          onOpenMemoryVault={() => {
            setIsSettingsOpen(false);
            setMemoryOpen(true);
          }}
          onDeleteAccount={handleDeleteAccount}
          onProfileUpdated={(updated) => setCurrentUser(updated)}
          language={language}
          setLanguage={setLanguage}
          currentUser={currentUser}
          autoRead={autoRead}
          setAutoRead={setAutoReadPersist}
          onOpenProfile={handleOpenProfile}
          selectedPatientId={selectedPatientId}
          dependents={dependents}
        />

        {isProfileOpen && (
          <Profile
            onClose={() => setIsProfileOpen(false)}
            darkMode={darkMode}
            initialTab={profileInitialTab}
            onProfileUpdated={refreshPatientContext}
            onDependentDeleted={handleDependentDeleted}
            profile={currentUser}
            dependents={dependents}
            selectedDependentId={selectedPatientId !== 'self' ? selectedPatientId : null}
          />
        )}
      </Suspense>

      <MemoryConsentModal
        isOpen={showMemoryConsentModal}
        onAllow={handleAllowMemory}
        onSkip={handleSkipMemory}
        darkMode={darkMode}
      />
    </div>
  );
}
