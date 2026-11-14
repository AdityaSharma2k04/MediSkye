import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import ChatApp from '../components/ChatApp';
import * as api from '../services/api';

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
  getDocumentChats: vi.fn().mockResolvedValue([
    {
      id: 'chat-alpha-1',
      session_id: 'session-alpha',
      session_title: 'Alpha Symptoms',
      role: 'user',
      message: 'Fever and headaches',
      timestamp: '2026-11-05T10:00:00Z',
    },
    {
      id: 'chat-alpha-2',
      session_id: 'session-alpha',
      session_title: 'Alpha Symptoms',
      role: 'assistant',
      message: 'Monitor temperature and hydrate.',
      timestamp: '2026-11-05T10:00:05Z',
    },
  ]),
  getGeneralChats: vi.fn().mockResolvedValue([
    {
      id: 'chat-alpha-1',
      session_id: 'session-alpha',
      session_title: 'Alpha Symptoms',
      role: 'user',
      message: 'Fever and headaches',
      timestamp: '2026-11-05T10:00:00Z',
    },
    {
      id: 'chat-beta-1',
      session_id: 'session-beta',
      session_title: 'Beta Diet Plan',
      role: 'user',
      message: 'Low sodium recommendations',
      timestamp: '2026-11-05T11:00:00Z',
    },
  ]),
  renameChatSession: vi.fn().mockResolvedValue({ session_id: 'session-alpha', title: 'Renamed Alpha' }),
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
}));

describe('ChatSessionSync — Multi-session standalone persistence across reloads', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('mediskye_sidebar_open', 'true');
    window.innerWidth = 1024;
  });

  it('reconstructs separate standalone conversations with custom titles from server', async () => {
    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // Verify getGeneralChats was called during refreshDocuments on mount
    await waitFor(() => {
      expect(api.getGeneralChats).toHaveBeenCalled();
    });

    // Both sessions should be rendered in the sidebar
    expect(await screen.findByText('Alpha Symptoms')).toBeInTheDocument();
    expect(await screen.findByText('Beta Diet Plan')).toBeInTheDocument();
  });

  it('selecting a standalone conversation loads history scoped to that session_id', async () => {
    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    const alphaItem = await screen.findByText('Alpha Symptoms');
    fireEvent.click(alphaItem);

    await waitFor(() => {
      expect(api.getDocumentChats).toHaveBeenCalledWith(null, 'session-alpha');
    });
  });
});

