import { describe, it, expect, vi, beforeEach } from 'vitest';
import {
  safeStorageSet,
  safeStorageGet,
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
});
