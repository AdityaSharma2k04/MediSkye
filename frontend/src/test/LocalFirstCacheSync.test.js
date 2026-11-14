import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  safeStorageSet,
  safeStorageGet,
  getStableCacheUid,
  getCachedProfile,
  setCachedProfile,
  getCachedDependents,
  setCachedDependents,
  getCachedDocuments,
  setCachedDocuments,
  getCachedDocMetrics,
  setCachedDocMetrics,
  getCachedDocSummary,
  setCachedDocSummary,
  getCachedMemoryFacts,
  setCachedMemoryFacts,
  getCachedTrends,
  setCachedTrends,
  getCachedConversations,
  setCachedConversations,
  purgePatientLocalCache,
  purgeDocumentLocalCache,
  prewarmPatientLocalCache,
  getProfile,
  getDependents,
  getUserDocuments,
  getDocuments,
  getDocumentChats,
  getGeneralChats,
  getCachedChatMessages,
  setCachedChatMessages,
} from '../services/api';

describe('Local-First Cache Manager (api.js)', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('safely gets and sets objects and primitives in localStorage', () => {
    safeStorageSet('test_key', { a: 1, b: 'two' });
    expect(safeStorageGet('test_key')).toEqual({ a: 1, b: 'two' });
    expect(safeStorageGet('non_existent', 'default')).toBe('default');
  });

  it('evicts LRU/temporary doc metrics and trends when quota is exceeded', () => {
    // Fill with temporary cached metrics
    localStorage.setItem('mediskye_cached_doc_metrics_doc1', JSON.stringify([{ name: 'Glucose' }]));
    localStorage.setItem('mediskye_cached_trends_uid_self', JSON.stringify({ series: [] }));
    localStorage.setItem('keep_important_key', 'keep_me');

    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');
    setItemSpy.mockImplementationOnce(() => {
      const err = new Error('QuotaExceededError');
      err.name = 'QuotaExceededError';
      throw err;
    });

    safeStorageSet('new_critical_item', { success: true });

    // Temporary keys should have been cleaned up
    expect(localStorage.getItem('mediskye_cached_doc_metrics_doc1')).toBeNull();
    expect(localStorage.getItem('mediskye_cached_trends_uid_self')).toBeNull();
    // Non-temporary item preserved
    expect(localStorage.getItem('keep_important_key')).toBe('keep_me');
    // New item successfully stored
    expect(safeStorageGet('new_critical_item')).toEqual({ success: true });

    setItemSpy.mockRestore();
  });

  it('stores and retrieves per-document metrics and summaries', () => {
    const docId = 'doc-123-abc';
    const sampleMetrics = [{ key: 'hba1c', name: 'HbA1c', value: 5.6 }];
    const sampleSummary = { key_findings: ['Normal glucose'] };

    setCachedDocMetrics(docId, sampleMetrics);
    setCachedDocSummary(docId, sampleSummary);

    expect(getCachedDocMetrics(docId)).toEqual(sampleMetrics);
    expect(getCachedDocSummary(docId)).toEqual(sampleSummary);

    purgeDocumentLocalCache(docId);
    expect(getCachedDocMetrics(docId)).toBeNull();
    expect(getCachedDocSummary(docId)).toBeNull();
  });

  it('stores and retrieves Memory Vault facts and trends per patient', () => {
    const factsSelf = [{ id: 'f1', fact_text: 'Mild asthma' }];
    const factsChild = [{ id: 'f2', fact_text: 'Amoxicillin allergy' }];

    setCachedMemoryFacts(factsSelf, 'self', 'test-uid');
    setCachedMemoryFacts(factsChild, 'dep-child', 'test-uid');

    expect(getCachedMemoryFacts('self', 'test-uid')).toEqual(factsSelf);
    expect(getCachedMemoryFacts('dep-child', 'test-uid')).toEqual(factsChild);

    const trendsSelf = { series: [{ key: 'wbc', points: [{ value: 6.2 }] }] };
    setCachedTrends(trendsSelf, 'self', 'test-uid');
    expect(getCachedTrends('self', 'test-uid')).toEqual(trendsSelf);

    // Purging dependent cache cleans only that dependent
    purgePatientLocalCache('dep-child', 'test-uid');
    expect(getCachedMemoryFacts('dep-child', 'test-uid')).toEqual([]);
    expect(getCachedMemoryFacts('self', 'test-uid')).toEqual(factsSelf);
  });

  it('stores and retrieves cached conversations for 0ms initial load', () => {
    const convs = [
      { id: 'sess-1', title: 'Checkup Notes', messages: [], patient_id: 'self' },
      { id: 'doc-report-1', title: 'CBC Report', messages: [], patient_id: 'self' },
    ];

    setCachedConversations(convs, 'self', 'user-456');
    expect(getCachedConversations('self', 'user-456')).toEqual(convs);

    purgePatientLocalCache('self', 'user-456');
    expect(getCachedConversations('self', 'user-456')).toBeNull();
  });

  it('prewarmPatientLocalCache executes without throwing', async () => {
    await expect(prewarmPatientLocalCache('self', [], [])).resolves.not.toThrow();
  });

  describe('Stable Offline UID Lookup & Offline Resilience', () => {
    it('resolves stable cache UID with proper fallback chain', () => {
      // 1. explicitUid
      expect(getStableCacheUid('explicit-123')).toBe('explicit-123');

      // 2. fallback to snapshot when no explicit UID
      localStorage.setItem('mediskye_auth_user_snapshot', JSON.stringify({ uid: 'snap-uid-456' }));
      expect(getStableCacheUid()).toBe('snap-uid-456');
      expect(localStorage.getItem('mediskye_last_uid')).toBe('snap-uid-456');

      // 3. fallback to mediskye_last_uid
      localStorage.removeItem('mediskye_auth_user_snapshot');
      expect(getStableCacheUid()).toBe('snap-uid-456');

      // 4. default when storage empty
      localStorage.clear();
      expect(getStableCacheUid()).toBe('default');
    });

    it('getCachedProfile and setCachedProfile support stable UID and flexible parameter ordering', () => {
      localStorage.setItem('mediskye_last_uid', 'user-offline-1');
      const profile = { id: 'user-offline-1', email: 'test@mediskye.com', full_name: 'Jane Doe' };

      // Normal order: (profile, uid)
      setCachedProfile(profile);
      expect(getCachedProfile()).toEqual(profile);

      // Inverted order: (uid, profile)
      const profile2 = { id: 'user-offline-2', full_name: 'John Doe' };
      setCachedProfile('user-offline-2', profile2);
      expect(getCachedProfile('user-offline-2')).toEqual(profile2);
    });

    it('getProfile returns cached profile when navigator is offline or fetch fails', async () => {
      const cached = { id: 'cached-user', email: 'offline@mediskye.com' };
      setCachedProfile(cached, 'test-offline-uid');
      localStorage.setItem('mediskye_last_uid', 'test-offline-uid');

      // Offline flag check
      const originalOnLine = navigator.onLine;
      try {
        Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
        const result = await getProfile();
        expect(result).toEqual(cached);
      } finally {
        Object.defineProperty(navigator, 'onLine', { value: originalOnLine, configurable: true });
      }
    });

    it('getDependents returns cached dependents when offline', async () => {
      const deps = [{ id: 'dep-1', full_name: 'Child One' }];
      setCachedDependents(deps, 'test-offline-uid');
      localStorage.setItem('mediskye_last_uid', 'test-offline-uid');

      const originalOnLine = navigator.onLine;
      try {
        Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
        const result = await getDependents();
        expect(result).toEqual(deps);
      } finally {
        Object.defineProperty(navigator, 'onLine', { value: originalOnLine, configurable: true });
      }
    });

    it('getUserDocuments and getDocuments return cached documents when offline', async () => {
      const docs = [{ id: 'doc-1', filename: 'report.pdf', title: 'Blood Work' }];
      setCachedDocuments(docs, 'self', 'test-offline-uid');
      localStorage.setItem('mediskye_last_uid', 'test-offline-uid');

      const originalOnLine = navigator.onLine;
      try {
        Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
        const resUserDocs = await getUserDocuments('self');
        const resDocs = await getDocuments('self');
        expect(resUserDocs).toEqual(docs);
        expect(resDocs).toEqual(docs);
      } finally {
        Object.defineProperty(navigator, 'onLine', { value: originalOnLine, configurable: true });
      }
    });

    it('getDocumentChats and getGeneralChats persist message histories when online and return cached messages when offline', async () => {
      const mockDocMessages = [
        { id: 'msg-1', role: 'user', message: 'What is my glucose?' },
        { id: 'msg-2', role: 'ai', message: 'Your glucose is 92 mg/dL.' },
      ];
      const mockGeneralMessages = [
        { id: 'msg-3', role: 'user', message: 'How much water should I drink?' },
        { id: 'msg-4', role: 'ai', message: 'Around 2 to 3 liters daily.' },
      ];

      localStorage.setItem('mediskye_last_uid', 'test-chat-uid');

      // 1. Online: fetch succeeds and stores messages in localStorage
      const originalFetch = globalThis.fetch;
      const fetchSpy = vi.fn().mockImplementation((url) => {
        if (url.includes('/documents/doc-abc/chats')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(mockDocMessages),
          });
        }
        if (url.includes('/users/me/chats?session_id=sess-xyz')) {
          return Promise.resolve({
            ok: true,
            status: 200,
            json: () => Promise.resolve(mockGeneralMessages),
          });
        }
        return Promise.resolve({ ok: false, status: 404 });
      });
      globalThis.fetch = fetchSpy;

      try {
        const docChats = await getDocumentChats('doc-abc');
        expect(docChats).toEqual(mockDocMessages);
        expect(getCachedChatMessages('doc_doc-abc')).toEqual(mockDocMessages);

        const genChats = await getGeneralChats('sess-xyz');
        expect(genChats).toEqual(mockGeneralMessages);
        expect(getCachedChatMessages('session_sess-xyz')).toEqual(mockGeneralMessages);
      } finally {
        globalThis.fetch = originalFetch;
      }

      // 2. Offline: navigator.onLine = false returns cached messages without network
      const originalOnLine = navigator.onLine;
      try {
        Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });
        const offlineDocChats = await getDocumentChats('doc-abc');
        expect(offlineDocChats).toEqual(mockDocMessages);

        const offlineGenChats = await getGeneralChats('sess-xyz');
        expect(offlineGenChats).toEqual(mockGeneralMessages);
      } finally {
        Object.defineProperty(navigator, 'onLine', { value: originalOnLine, configurable: true });
      }
    });
  });
});
