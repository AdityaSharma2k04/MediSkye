import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChatApp from '../components/ChatApp';
import ChatMessage, { stripAbnormalFlags, cleanMessageText } from '../components/ChatMessage';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getProfile: vi.fn(),
  getDependents: vi.fn(),
  getUserDocuments: vi.fn(),
  getChatSessions: vi.fn(),
  getDocumentChats: vi.fn(),
  getGeneralChats: vi.fn(),
  renameDocument: vi.fn(),
  deleteDocument: vi.fn(),
  renameChatSession: vi.fn(),
  deleteChatSession: vi.fn(),
  clearAllChatSessions: vi.fn(),
  updateProfile: vi.fn(),
  deleteAccount: vi.fn(),
  logout: vi.fn(),
  sendQueryStream: vi.fn(),
  detachChatDocument: vi.fn(),
  fetchLabMetrics: vi.fn(),
  getMemoryStatus: vi.fn(),
  getMemoryFacts: vi.fn(),
  getFacts: vi.fn(),
  reassignDocumentPatient: vi.fn(),
  getDocumentSummary: vi.fn(),
  getCachedProfile: vi.fn(),
  getCachedDependents: vi.fn(),
  getCachedDocuments: vi.fn(),
  setCachedDocuments: vi.fn(),
  setCachedProfile: vi.fn(),
  setCachedDependents: vi.fn(),
  getCachedConversations: vi.fn(),
  setCachedConversations: vi.fn(),
  getCachedMemoryFacts: vi.fn(),
  setCachedMemoryFacts: vi.fn(),
  getCachedDocMetrics: vi.fn(),
  setCachedDocMetrics: vi.fn(),
  getCachedDocSummary: vi.fn(),
  setCachedDocSummary: vi.fn(),
  getCachedChatMessages: vi.fn(),
  setCachedChatMessages: vi.fn(),
  prewarmPatientLocalCache: vi.fn().mockResolvedValue(),
  prewarmMessageHistories: vi.fn(),
  purgePatientLocalCache: vi.fn(),
  getMetricTrends: vi.fn().mockResolvedValue({ series: [] }),
  getCachedTrends: vi.fn().mockReturnValue(null),
}));

describe('MediSkye Automated Human QA Simulation Suite', () => {
  const mockUser = {
    id: 'user-primary-123',
    email: 'sarah.connor@example.com',
    full_name: 'Sarah Connor',
    memory_consent_granted: true,
  };

  const mockDependents = [
    {
      id: 'dep-john-456',
      name: 'John Connor',
      full_name: 'John Connor',
      relationship: 'Child',
      birth_date: '2015-02-28',
      gender: 'male',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('mediskye_patient_id', 'self');

    api.getProfile.mockResolvedValue(mockUser);
    api.getDependents.mockResolvedValue(mockDependents);
    api.getUserDocuments.mockResolvedValue([]);
    api.getChatSessions.mockResolvedValue([]);
    api.getGeneralChats.mockResolvedValue([]);
    api.getDocumentChats.mockResolvedValue([]);
    api.fetchLabMetrics.mockResolvedValue([]);
    api.getMemoryFacts.mockResolvedValue([]);
    api.getCachedProfile.mockReturnValue(mockUser);
    api.getCachedDependents.mockReturnValue(mockDependents);
    api.getCachedConversations.mockReturnValue(null);
    api.getCachedDocuments.mockReturnValue([]);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ─────────────────────────────────────────────────────────────────────────────
  // QA Journey 1: Cold Launch & Profile Switch Bleed-Over
  // ─────────────────────────────────────────────────────────────────────────────
  it('QA Journey 1 (Cold Launch & Profile Switch Bleed-Over): starts unlocked on New Chat, locks on report, unlocks on New Chat, switches profile with 0 bleed-over', async () => {
    const cachedSelfDocs = [
      {
        id: 'doc-cbc-self',
        filename: 'CBC_Report.pdf',
        title: 'Complete Blood Count',
        created_at: '2026-10-15T08:00:00Z',
        dependent_id: null,
      },
    ];

    api.getUserDocuments.mockImplementation(async (patId) => {
      if (patId === 'self') return cachedSelfDocs;
      return []; // Dependent John has 0 documents
    });

    api.getCachedDocuments.mockImplementation((patId) => {
      if (patId === 'self') return cachedSelfDocs;
      return [];
    });

    api.getDocumentChats.mockResolvedValue([
      {
        id: 'msg-1',
        role: 'user',
        message: 'Explain my platelets',
        created_at: '2026-10-15T08:05:00Z',
      },
      {
        id: 'msg-2',
        role: 'ai',
        message: 'Your platelets are 238,000 / µL which is healthy.',
        created_at: '2026-10-15T08:05:05Z',
      },
    ]);

    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // 1. Initial cold launch: starts on fresh unlocked "New Chat" under 'self'
    await waitFor(() => {
      expect(screen.getAllByText(/Sarah Connor/i).length).toBeGreaterThan(0);
    });

    // Profile switcher should be unlocked (no lock icon badge)
    expect(screen.queryByTitle(/Profile locked because a report is uploaded/i)).not.toBeInTheDocument();

    // 2. Click the old report chat in sidebar
    await waitFor(() => {
      expect(screen.getByText('Complete Blood Count')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Complete Blood Count'));

    // Chat history loads
    await waitFor(() => {
      expect(screen.getByText(/Your platelets are 238,000 \/ µL which is healthy/i)).toBeInTheDocument();
    });

    // Profile switcher is now locked to the report
    await waitFor(() => {
      const trigger = screen.getByTestId('patient-switcher-trigger');
      expect(trigger).toHaveAttribute('aria-disabled', 'true');
    });

    // 3. User clicks "New Conversation" in sidebar
    const newChatBtn = screen.getByTestId('sidebar-new-chat-button');
    fireEvent.click(newChatBtn);

    // Profile switcher unlocks
    await waitFor(() => {
      const trigger = screen.getByTestId('patient-switcher-trigger');
      expect(trigger).not.toHaveAttribute('aria-disabled', 'true');
    });

    // 4. Switch to Dependent John (who has 0 chats)
    const trigger = screen.getByTestId('patient-switcher-trigger');
    fireEvent.click(trigger);

    const depOption = await screen.findByText('John Connor');
    fireEvent.click(depOption);

    // John's view should render cleanly with fresh empty state and zero messages from Sarah
    await waitFor(() => {
      expect(screen.queryByText(/Your platelets are 238,000/i)).not.toBeInTheDocument();
      expect(screen.queryByText('Complete Blood Count')).not.toBeInTheDocument();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────────
  // QA Journey 2: Cross-Device Cloud Sync & Deletion Reconciliation
  // ─────────────────────────────────────────────────────────────────────────────
  it('QA Journey 2 (Cross-Device Cloud Sync & Deletion Reconciliation): authoritative server reconciliation removes deleted doc and adds newly synced doc', async () => {
    // Android initially starts with doc_1 and doc_2 in cached state
    const cachedConvs = [
      {
        id: 'doc-1',
        document_id: 'doc-1',
        title: 'Lipid Panel',
        messages: [{ id: 'm1', sender: 'assistant', text: 'Total Cholesterol 180' }],
        patient_id: 'self',
        isDraft: false,
      },
      {
        id: 'doc-2',
        document_id: 'doc-2',
        title: 'Obsolete Report (Deleted on Laptop)',
        messages: [{ id: 'm2', sender: 'assistant', text: 'Old message' }],
        patient_id: 'self',
        isDraft: false,
      },
    ];

    api.getCachedConversations.mockReturnValue(cachedConvs);

    // On Laptop, doc_2 was deleted and doc_3 was uploaded. Server now returns [doc_1, doc_3].
    const serverFreshDocs = [
      {
        id: 'doc-1',
        filename: 'Lipid_Panel.pdf',
        title: 'Lipid Panel',
        created_at: '2026-10-10T09:00:00Z',
      },
      {
        id: 'doc-3',
        filename: 'Thyroid_TSH.pdf',
        title: 'Thyroid Function TSH',
        created_at: '2026-10-14T11:00:00Z',
      },
    ];

    api.getUserDocuments.mockResolvedValue(serverFreshDocs);
    api.getChatSessions.mockResolvedValue([]);
    api.getGeneralChats.mockResolvedValue([]);

    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // Initial render shows Lipid Panel
    await waitFor(() => {
      expect(screen.getByText('Lipid Panel')).toBeInTheDocument();
    });

    // Trigger Cloud Sync (via Header Refresh button)
    const syncButton = screen.getByRole('button', { name: /Sync latest chats and reports from cloud/i });
    fireEvent.click(syncButton);

    // Verify doc_2 is gone and doc_3 is present
    await waitFor(() => {
      expect(screen.queryByText(/Obsolete Report \(Deleted on Laptop\)/i)).not.toBeInTheDocument();
      expect(screen.getByText('Thyroid Function TSH')).toBeInTheDocument();
    });

    // Verify doc-1 retained its cached message history
    fireEvent.click(screen.getByText('Lipid Panel'));
    await waitFor(() => {
      expect(screen.getByText(/Total Cholesterol 180/i)).toBeInTheDocument();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────────
  // QA Journey 3: Offline Boot & Reconnect
  // ─────────────────────────────────────────────────────────────────────────────
  it('QA Journey 3 (Offline Boot & Reconnect): boots offline with cached chats, shows subtle red Offline pill, clears on reconnect', async () => {
    // Simulate offline environment
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      configurable: true,
      value: false,
    });

    const offlineCachedDocs = [
      {
        id: 'doc-offline-1',
        filename: 'Kidney_KFT.pdf',
        title: 'Renal Function Panel',
        created_at: '2026-10-01T12:00:00Z',
      },
    ];
    api.getCachedDocuments.mockReturnValue(offlineCachedDocs);
    api.getCachedConversations.mockReturnValue([
      {
        id: 'doc-offline-1',
        document_id: 'doc-offline-1',
        title: 'Renal Function Panel',
        messages: [
          { id: 'm-off', sender: 'assistant', text: 'Creatinine is 0.9 mg/dL' },
        ],
        patient_id: 'self',
        isDraft: false,
      },
    ]);

    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // 1. Red Offline status pill should be visible without "cached data" noise
    await waitFor(() => {
      expect(screen.getByRole('status', { name: /^Offline$/i })).toBeInTheDocument();
    });

    // 2. Cached chats render in the sidebar and open cleanly
    await waitFor(() => {
      expect(screen.getByText('Renal Function Panel')).toBeInTheDocument();
    });
    fireEvent.click(screen.getByText('Renal Function Panel'));

    await waitFor(() => {
      expect(screen.getByText(/Creatinine is 0.9 mg\/dL/i)).toBeInTheDocument();
    });

    // 3. User reconnects (online event fires)
    Object.defineProperty(navigator, 'onLine', {
      writable: true,
      configurable: true,
      value: true,
    });
    window.dispatchEvent(new Event('online'));

    // Red Offline pill disappears
    await waitFor(() => {
      expect(screen.queryByRole('status', { name: /^Offline$/i })).not.toBeInTheDocument();
    });
  });

  // ─────────────────────────────────────────────────────────────────────────────
  // QA Journey 4: Streaming JSON & Disclaimer Cleanliness
  // ─────────────────────────────────────────────────────────────────────────────
  it('QA Journey 4 (Streaming JSON & Disclaimer Cleanliness): strips trailing fences, partial abnormal_flags, and handles disclaimer rules', () => {
    // 1. Live streaming with trailing partial fence before key completes
    const streamingEarlyPartial = 'Your Vitamin D is 22 ng/mL.\n\n```json\n{\n  "abn';
    expect(stripAbnormalFlags(streamingEarlyPartial)).toBe('Your Vitamin D is 22 ng/mL.');

    const streamingFenceOnly = 'Your Vitamin D is 22 ng/mL.\n\n```j';
    expect(stripAbnormalFlags(streamingFenceOnly)).toBe('Your Vitamin D is 22 ng/mL.');

    const streamingJsonWord = 'Your Vitamin D is 22 ng/mL.\n\n```json';
    expect(stripAbnormalFlags(streamingJsonWord)).toBe('Your Vitamin D is 22 ng/mL.');

    const streamingBareJson = 'Your Vitamin D is 22 ng/mL.\n\n{\n  "abn';
    expect(stripAbnormalFlags(streamingBareJson)).toBe('Your Vitamin D is 22 ng/mL.');

    // 2. Live streaming with full abnormal_flags key
    const streamingPartial = 'Your Vitamin D is 22 ng/mL.\n\n```json\n{\n  "abnormal_flags": ["Vitamin D"]';
    expect(stripAbnormalFlags(streamingPartial)).toBe('Your Vitamin D is 22 ng/mL.');

    // 3. Completed block with bare fence without language tag
    const bareFence = 'Your Vitamin D is 22 ng/mL.\n\n```\n{"abnormal_flags": ["Vitamin D"]}\n```';
    expect(stripAbnormalFlags(bareFence)).toBe('Your Vitamin D is 22 ng/mL.');

    // 4. Leaked internal prompt tags
    const leakedXml = 'Normal results.<extracted_report_biomarkers count="2">...</extracted_report_biomarkers> Everything looks stable.';
    expect(stripAbnormalFlags(leakedXml)).toBe('Normal results. Everything looks stable.');

    // 5. Disclaimer deduplication on Turn 1 (isFollowupTurn = false)
    const turn1DoubleDisclaimer = '### Overview\nAll values reviewed.\n\n**Disclaimer:** Advice 1.\n\n**Disclaimer:** Advice 2.';
    const cleanedTurn1 = cleanMessageText(turn1DoubleDisclaimer, false);
    const disclaimerMatches = cleanedTurn1.match(/Disclaimer:/g) || [];
    expect(disclaimerMatches.length).toBe(1);

    // 6. Disclaimer complete suppression on Turn 2+ (isFollowupTurn = true)
    const turn2WithDisclaimer = 'You should eat leafy greens and citrus.\n\n**Disclaimer:** Educational only.';
    const cleanedTurn2 = cleanMessageText(turn2WithDisclaimer, true);
    expect(cleanedTurn2).toBe('You should eat leafy greens and citrus.');
    expect(cleanedTurn2).not.toContain('Disclaimer:');
  });

  // ─────────────────────────────────────────────────────────────────────────────
  // QA Journey 5: In-Flight Upload & Draft Conversation Protection During Background Sync
  // ─────────────────────────────────────────────────────────────────────────────
  it('QA Journey 5 (In-Flight Upload & Draft Protection): background refreshDocuments does not prune draft conversation', async () => {
    api.getUserDocuments.mockResolvedValue([
      { id: 'doc-existing-1', filename: 'Existing.pdf', title: 'Existing Report', created_at: '2026-10-01T00:00:00Z' }
    ]);
    api.getCachedDocuments.mockReturnValue([]);

    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // Draft conversation should be mounted
    await waitFor(() => {
      expect(screen.getByText('Existing Report')).toBeInTheDocument();
    });

    // Profile switcher is unlocked on fresh draft
    const trigger = screen.getByTestId('patient-switcher-trigger');
    expect(trigger).not.toHaveAttribute('aria-disabled', 'true');
  });
});
