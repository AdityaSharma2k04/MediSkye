import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import ChatApp from '../components/ChatApp';

vi.mock('../services/api', () => ({
  getProfile: vi.fn().mockResolvedValue({
    id: 'test-user-id',
    email: 'test@example.com',
    full_name: 'Test Patient',
    memory_consent_granted: true,
  }),
  getDependents: vi.fn().mockResolvedValue([]),
  getUserDocuments: vi.fn().mockResolvedValue([]),
  getChatSessions: vi.fn().mockResolvedValue([]),
  getDocumentChats: vi.fn().mockResolvedValue([]),
  getGeneralChats: vi.fn().mockResolvedValue([]),
  renameChatSession: vi.fn(),
  deleteChatSession: vi.fn().mockResolvedValue(true),
  clearAllChatSessions: vi.fn().mockResolvedValue(true),
  updateProfile: vi.fn(),
  deleteAccount: vi.fn(),
  logout: vi.fn(),
  sendQueryStream: vi.fn(),
  detachChatDocument: vi.fn(),
  fetchLabMetrics: vi.fn().mockResolvedValue([]),
  getMemoryStatus: vi.fn().mockResolvedValue({ memory_consent_granted: true }),
  getMemoryFacts: vi.fn().mockResolvedValue([]),
  getFacts: vi.fn().mockResolvedValue([]),
  reassignDocumentPatient: vi.fn().mockResolvedValue({ status: 'ok' }),
  getCachedProfile: vi.fn().mockReturnValue(null),
  getCachedDependents: vi.fn().mockReturnValue([]),
  getCachedDocuments: vi.fn().mockReturnValue([]),
  setCachedDocuments: vi.fn(),
  setCachedProfile: vi.fn(),
  setCachedDependents: vi.fn(),
  getCachedConversations: vi.fn().mockReturnValue(null),
  setCachedConversations: vi.fn(),
  getCachedMemoryFacts: vi.fn().mockReturnValue([]),
  setCachedMemoryFacts: vi.fn(),
  getCachedDocMetrics: vi.fn().mockReturnValue(null),
  setCachedDocMetrics: vi.fn(),
  getCachedDocSummary: vi.fn().mockReturnValue(null),
  setCachedDocSummary: vi.fn(),
  getCachedTrends: vi.fn().mockReturnValue(null),
  setCachedTrends: vi.fn(),
  prewarmPatientLocalCache: vi.fn(),
  syncSingleProfileToLocalCache: vi.fn().mockResolvedValue({ docs: [], conversations: [] }),
  emitConnectivityStatus: vi.fn(),
  checkConnectivity: vi.fn().mockResolvedValue(true),
  API_BASE_URL: 'http://localhost:8000',
}));

describe('WorkbenchHeader desktop vs mobile/tablet sidebar toggle', () => {
  const originalInnerWidth = window.innerWidth;

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    window.innerWidth = originalInnerWidth;
  });

  it.each([1920, 1366, 1024])(
    'does NOT render header "Toggle sidebar" button at desktop width %ipx while keeping Sidebar/NavRail control',
    async (width) => {
      window.innerWidth = width;
      localStorage.setItem('mediskye_sidebar_open', 'true');

      render(
        <MemoryRouter>
          <ChatApp />
        </MemoryRouter>
      );

      const header = await screen.findByTestId('workbench-header');
      expect(within(header).queryByRole('button', { name: /toggle sidebar/i })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: /toggle sidebar/i })).not.toBeInTheDocument();

      const collapseBtn = screen.queryByRole('button', { name: /collapse sidebar/i });
      const expandBtn = screen.queryByRole('button', { name: /expand sidebar/i });
      expect(Boolean(collapseBtn || expandBtn)).toBe(true);
    }
  );

  it.each([1023, 768, 390])(
    'renders exactly ONE "Toggle sidebar" button in the header at tablet/mobile width %ipx',
    async (width) => {
      window.innerWidth = width;

      render(
        <MemoryRouter>
          <ChatApp />
        </MemoryRouter>
      );

      const header = await screen.findByTestId('workbench-header');
      const toggleButtons = within(header).getAllByRole('button', { name: /toggle sidebar/i });
      expect(toggleButtons).toHaveLength(1);
      expect(screen.getAllByRole('button', { name: /toggle sidebar/i })).toHaveLength(1);
    }
  );
});
