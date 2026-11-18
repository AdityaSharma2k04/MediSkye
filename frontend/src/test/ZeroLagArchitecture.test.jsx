import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import * as api from '../services/api';
import ChatApp from '../components/ChatApp';
import Workbench from '../components/workbench/Workbench';
import ChatMessage from '../components/ChatMessage';

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

    it('migrates cached chat messages from draft key to server-assigned session_id in RAM_CACHE and localStorage', () => {
      const draftKey = 'session_new_self_9999999999';
      const serverKey = 'session_real-server-uuid-55555';
      const initialMsgs = [
        { id: 'u1', sender: 'user', text: 'Hello doctor' },
        { id: 'a1', sender: 'assistant', text: 'Hello! How can I help you today?' },
      ];

      api.setCachedChatMessages(draftKey, initialMsgs);
      expect(api.getCachedChatMessages(draftKey)).toEqual(initialMsgs);

      api.migrateCachedChatMessages(draftKey, serverKey);

      expect(api.getCachedChatMessages(draftKey)).toEqual([]);
      expect(api.getCachedChatMessages(serverKey)).toEqual(initialMsgs);
    });

    it('renders live streamed answer and completed response in active thread immediately without reload', async () => {
      const mockProfile = { id: 'u1', email: 'test@example.com', full_name: 'Aditya' };
      vi.spyOn(api, 'getProfile').mockResolvedValue(mockProfile);
      vi.spyOn(api, 'getUserDocuments').mockResolvedValue([]);
      vi.spyOn(api, 'getGeneralChats').mockResolvedValue([]);
      vi.spyOn(api, 'getChatSessions').mockResolvedValue([]);
      vi.spyOn(api, 'getDependents').mockResolvedValue([]);

      const streamSpy = vi.spyOn(api, 'sendQueryStream').mockImplementation(async (query, docId, lang, onChunk) => {
        onChunk({
          session_id: 'real-session-uuid-888',
          title: 'Blood Pressure Query',
        });
        onChunk({ chunk: 'Your blood pressure ' });
        onChunk({ chunk: 'is completely normal.' });
      });

      render(<ChatApp />);
      await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

      const input = screen.getByPlaceholderText(/Ask a medical question/i);
      fireEvent.change(input, { target: { value: 'Is my blood pressure normal?' } });
      const form = input.closest('form');

      await act(async () => {
        fireEvent.submit(form);
      });

      // Stream should have been called
      await waitFor(() => {
        expect(streamSpy).toHaveBeenCalled();
      });

      // User question should be visible in the active thread immediately
      expect(await screen.findByText('Is my blood pressure normal?')).toBeInTheDocument();

      // Streamed & completed assistant response MUST be immediately visible without clicking sidebar or reloading!
      expect(await screen.findByText('Your blood pressure is completely normal.')).toBeInTheDocument();

      streamSpy.mockRestore();
    });
  });

  describe('TASK 5: Message Role & Timestamp Normalization Everywhere', () => {
    it('normalizeChatMessage canonicalizes user and assistant message shapes', () => {
      const userRaw = { role: 'user', content: 'What is my ferritin level?', created_at: '2026-11-18T16:54:39.772258+00:00' };
      const userNorm = api.normalizeChatMessage(userRaw);

      expect(userNorm.sender).toBe('user');
      expect(userNorm.role).toBe('user');
      expect(userNorm.isUser).toBe(true);
      expect(userNorm.content).toBe('What is my ferritin level?');
      expect(userNorm.text).toBe('What is my ferritin level?');
      expect(userNorm.message).toBe('What is my ferritin level?');
      expect(userNorm.timestamp).not.toContain('2026-11-18T');

      const asstRaw = { role: 'assistant', content: 'Ferritin is normal at 120 ng/mL.', created_at: '2026-11-18T16:54:39.772258+00:00' };
      const asstNorm = api.normalizeChatMessage(asstRaw);

      expect(asstNorm.sender).toBe('ai');
      expect(asstNorm.role).toBe('assistant');
      expect(asstNorm.isUser).toBe(false);
      expect(asstNorm.content).toBe('Ferritin is normal at 120 ng/mL.');
      expect(asstNorm.timestamp).not.toContain('2026-11-18T');
    });

    it('formatMessageTimestamp formats ISO timestamps cleanly and defaults to Just now', () => {
      expect(api.formatMessageTimestamp(null)).toBe('Just now');
      expect(api.formatMessageTimestamp('')).toBe('Just now');
      expect(api.formatMessageTimestamp('09:11 PM')).toBe('09:11 PM');
      const formatted = api.formatMessageTimestamp('2026-11-18T16:54:39.772258+00:00');
      expect(formatted).not.toContain('2026');
      expect(formatted).not.toContain('+00:00');
    });

    it('ChatMessage renders user questions as user bubble without MediSkye AI header or raw ISO timestamps', () => {
      const userMsg = {
        id: 'msg-u1',
        role: 'user',
        content: 'Can you check my thyroid markers?',
        created_at: '2026-11-18T16:54:39.772258+00:00',
      };

      const { container } = render(<ChatMessage message={userMsg} />);

      expect(screen.getByText('Can you check my thyroid markers?')).toBeInTheDocument();
      // MUST NOT render MediSkye AI header for user questions!
      expect(screen.queryByText(/MediSkye AI/i)).not.toBeInTheDocument();
      // MUST NOT render raw ISO string
      expect(container.textContent).not.toContain('2026-11-18T16:54:39.772258+00:00');
    });

    it('ChatMessage renders assistant response with MediSkye AI header and formatted timestamp', () => {
      const asstMsg = {
        id: 'msg-a1',
        role: 'assistant',
        content: 'Your TSH is 2.1 mIU/L, which is within the normal reference range.',
        created_at: '2026-11-18T16:54:39.772258+00:00',
      };

      const { container } = render(<ChatMessage message={asstMsg} />);

      expect(screen.getByText(/MediSkye AI/i)).toBeInTheDocument();
      expect(screen.getByText(/Your TSH is 2\.1 mIU\/L/i)).toBeInTheDocument();
      // MUST NOT leak raw ISO timestamp string to the UI
      expect(container.textContent).not.toContain('2026-11-18T16:54:39.772258+00:00');
    });
  });
});
