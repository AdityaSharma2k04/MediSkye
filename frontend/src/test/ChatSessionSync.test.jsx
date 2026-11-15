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
  getCachedConversations: vi.fn((pid) => {
    try {
      const raw = localStorage.getItem(`mediskye_conversations_guest_${pid || 'self'}`);
      if (!raw) return null;
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        return parsed.map((c) => ({
          ...c,
          messages: Array.isArray(c.messages)
            ? c.messages.filter((m) => !m.isStreaming || (m.text && String(m.text).trim()))
            : [],
        }));
      }
      return parsed;
    } catch (_) {
      return null;
    }
  }),
  setCachedConversations: vi.fn((convs, pid) => {
    try {
      if (Array.isArray(convs)) {
        const sanitized = convs.map((c) => ({
          ...c,
          messages: Array.isArray(c.messages)
            ? c.messages
                .filter((m) => !m.isStreaming || (m.text && String(m.text).trim()))
                .map((m) => (m.isStreaming ? { ...m, isStreaming: false, statusText: null } : m))
            : [],
        }));
        localStorage.setItem(`mediskye_conversations_guest_${pid || 'self'}`, JSON.stringify(sanitized));
        return;
      }
      localStorage.setItem(`mediskye_conversations_guest_${pid || 'self'}`, JSON.stringify(convs));
    } catch (_) {}
  }),
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
  userKey: vi.fn((prefix, uid) => `${prefix}_${uid || 'default'}`),
  getCurrentUid: vi.fn(() => 'u_test'),
  syncAllProfilesInBackground: vi.fn().mockResolvedValue({ success: true }),
  emitConnectivityStatus: vi.fn(),
  checkConnectivity: vi.fn().mockResolvedValue(true),
  API_BASE_URL: 'http://localhost:8000',
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

  it('Stuck Streaming Skeleton Recovery on App Restart: immediately cleans up stuck skeleton and reconciles with server assistant reply', async () => {
    const stuckConversation = {
      id: 'session-alpha',
      title: 'Health Query',
      patient_id: 'self',
      messages: [
        { id: 'u1', sender: 'user', text: 'no', timestamp: '10:00 AM' },
        { id: 'bot-stuck', sender: 'bot', text: '', isStreaming: true, statusText: 'Checking your health history...', timestamp: '10:00 AM' },
      ],
      pdf: null,
      isDraft: false,
    };

    localStorage.setItem('mediskye_conversations_guest_self', JSON.stringify([stuckConversation]));

    api.getDocumentChats.mockResolvedValue([
      {
        id: 'msg-u1',
        session_id: 'session-alpha',
        role: 'user',
        message: 'no',
        created_at: '2026-11-05T10:00:00Z',
      },
      {
        id: 'msg-a1',
        session_id: 'session-alpha',
        role: 'assistant',
        message: 'No problem at all! Feel free to reach out anytime.',
        created_at: '2026-11-05T10:00:05Z',
      },
    ]);

    api.getGeneralChats.mockResolvedValue([
      {
        id: 'msg-u1',
        session_id: 'session-alpha',
        session_title: 'Health Query',
        role: 'user',
        message: 'no',
        created_at: '2026-11-05T10:00:00Z',
      },
      {
        id: 'msg-a1',
        session_id: 'session-alpha',
        session_title: 'Health Query',
        role: 'assistant',
        message: 'No problem at all! Feel free to reach out anytime.',
        created_at: '2026-11-05T10:00:05Z',
      },
    ]);

    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // 1. Verify "Checking your health history..." is NOT rendered as an infinite skeleton
    expect(screen.queryByText('Checking your health history...')).not.toBeInTheDocument();

    // 2. Select the conversation
    const sessionItem = await screen.findByText('Health Query');
    fireEvent.click(sessionItem);

    // 3. Verify server's completed response replaces the stuck skeleton
    await waitFor(() => {
      expect(screen.getByText('No problem at all! Feel free to reach out anytime.')).toBeInTheDocument();
    });

    // 4. Verify localStorage has been updated without any stuck skeleton
    const rawSaved = localStorage.getItem('mediskye_conversations_guest_self');
    expect(rawSaved).not.toBeNull();
    const saved = JSON.parse(rawSaved);
    const alphaSaved = saved.find((c) => c.id === 'session-alpha');
    expect(alphaSaved).toBeDefined();
    expect(alphaSaved.messages.some((m) => m.statusText === 'Checking your health history...')).toBe(false);
  });
});

