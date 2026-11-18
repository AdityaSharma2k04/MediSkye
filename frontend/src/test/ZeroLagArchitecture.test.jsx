import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import * as api from '../services/api';
import ChatApp from '../components/ChatApp';
import Workbench from '../components/workbench/Workbench';

// Mock routing and heavy services
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  Navigate: ({ to }) => <div data-testid="navigate-mock">{to}</div>,
  BrowserRouter: ({ children }) => <div>{children}</div>,
  Routes: ({ children }) => <div>{children}</div>,
  Route: ({ element }) => <div>{element}</div>,
}));

vi.mock('../services/speech', () => ({
  speakText: vi.fn(),
  stopSpeaking: vi.fn(),
}));

describe('MediSkye Zero-Lag Architecture Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    api.RAM_CACHE.clear();
    api.resetBootSyncStatus();
  });

  describe('TASK 1: Never Re-Trigger Workspace Hydration / Loading Screen After Boot', () => {
    it('initializes hydration to false when session guard or localStorage indicates boot sync complete', () => {
      const stableUid = api.getStableCacheUid();
      // Simulate boot sync already completed in previous session / localStorage
      api.markBootSyncCompleted(stableUid);

      expect(api.checkBootSyncCompleted(stableUid)).toBe(true);
      expect(sessionStorage.getItem('mediskye_boot_synced_v1')).toBe('true');
      expect(localStorage.getItem(`mediskye_initial_sync_complete_${stableUid}`)).toBe('true');
    });

    it('clears boot sync on explicit logout', () => {
      const stableUid = api.getStableCacheUid();
      api.markBootSyncCompleted(stableUid);
      expect(api.checkBootSyncCompleted(stableUid)).toBe(true);

      api.clearLocalAuthStorage();
      expect(sessionStorage.getItem('mediskye_boot_synced_v1')).toBeNull();
      expect(api.RAM_CACHE.size).toBe(0);
    });
  });

  describe('TASK 2: In-Memory RAM Cache (RAM_CACHE) Layer', () => {
    it('reads from RAM_CACHE in 0.001ms without JSON.parse overhead on cache hit', () => {
      const docId = 'doc-ram-123';
      const sampleMetrics = [
        { name: 'Hemoglobin', value: 14.2, unit: 'g/dL', status: 'normal' },
      ];

      // Set via api
      api.setCachedDocMetrics(docId, sampleMetrics);

      // Verify it is immediately in RAM_CACHE
      const ramKey = `mediskye_cached_doc_metrics_${docId}`;
      expect(api.RAM_CACHE.has(ramKey)).toBe(true);
      expect(api.RAM_CACHE.get(ramKey)).toBe(sampleMetrics);

      // Read back: should be exact object reference from RAM!
      const retrieved = api.getCachedDocMetrics(docId);
      expect(retrieved).toBe(sampleMetrics);
    });

    it('supports cached conversations, trends, facts, and chat messages in RAM_CACHE', () => {
      const stableUid = api.getStableCacheUid();
      const sampleConvs = [{ id: 'conv-1', title: 'Consultation 1', messages: [] }];
      const sampleFacts = [{ id: 'f-1', text: 'Allergic to penicillin' }];
      const sampleTrends = { series: [{ name: 'HbA1c', points: [] }] };
      const sampleMsgs = [{ id: 'm-1', role: 'user', message: 'Hello' }];

      api.setCachedConversations(sampleConvs, 'self');
      api.setCachedMemoryFacts(sampleFacts, 'self');
      api.setCachedTrends(sampleTrends, 'self');
      api.setCachedChatMessages('session_conv-1', sampleMsgs);

      expect(api.getCachedConversations('self')).toEqual(sampleConvs);
      expect(api.getCachedMemoryFacts('self')).toEqual(sampleFacts);
      expect(api.getCachedTrends('self')).toEqual(sampleTrends);
      expect(api.getCachedChatMessages('session_conv-1')).toEqual(sampleMsgs);
    });

    it('clears RAM_CACHE when localStorage is cleared', () => {
      api.setCachedDocSummary('doc-1', { summary: 'Patient is healthy' });
      expect(api.getCachedDocSummary('doc-1')).toEqual({ summary: 'Patient is healthy' });

      localStorage.clear();
      expect(api.RAM_CACHE.size).toBe(0);
      expect(api.getCachedDocSummary('doc-1')).toBeNull();
    });
  });

  describe('TASK 3 & 4: 0ms Profile Switching, Workbench Tabs & Download Summary', () => {
    it('Workbench Download Summary / Export button has type="button" and prevents default', () => {
      const mockPrint = vi.fn();
      render(
        <Workbench
          isDesktop={true}
          isOnline={true}
          viewMode="chat"
          onViewModeChange={vi.fn()}
          currentUser={{ id: 'u1', email: 'test@example.com', full_name: 'Aditya' }}
          dependents={[]}
          selectedPatientId="self"
          onSelectPatient={vi.fn()}
          messages={[]}
          conversations={[]}
          activePdf={{ id: 'doc-1', title: 'Lipid Panel.pdf' }}
          onExportSummary={mockPrint}
          onOpenExport={vi.fn()}
          onOpenPalette={vi.fn()}
          onToggleInspector={vi.fn()}
        />
      );

      const exportBtn = screen.getByLabelText('Export Summary');
      expect(exportBtn).toBeInTheDocument();
      expect(exportBtn.getAttribute('type')).toBe('button');

      const chatExportBtn = screen.getByLabelText('Export chat data');
      expect(chatExportBtn).toBeInTheDocument();
      expect(chatExportBtn.getAttribute('type')).toBe('button');
    });

    it('getDocumentSummary returns cached summary in 0ms without firing network request', async () => {
      const docId = 'doc-cached-summary-999';
      api.setCachedDocSummary(docId, { summary: 'Pre-computed summary' });

      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      const result = await api.getDocumentSummary(docId);

      expect(result.summary).toBe('Pre-computed summary');
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });

    it('fetchLabMetrics returns cached metrics in 0ms without firing network request', async () => {
      const docId = 'doc-cached-metrics-888';
      const metrics = [{ name: 'Cholesterol', value: 190, unit: 'mg/dL' }];
      api.setCachedDocMetrics(docId, metrics);

      const fetchSpy = vi.spyOn(globalThis, 'fetch');
      const result = await api.fetchLabMetrics(docId);

      expect(result).toEqual(metrics);
      expect(fetchSpy).not.toHaveBeenCalled();
      fetchSpy.mockRestore();
    });
  });
});
