import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import ChatApp from '../components/ChatApp';

vi.mock('../services/api', () => ({
  getProfile: vi.fn().mockResolvedValue({ id: 'u1', email: 'test@example.com' }),
  getDependents: vi.fn().mockResolvedValue([]),
  getUserDocuments: vi.fn().mockResolvedValue([]),
  getDocumentChats: vi.fn().mockResolvedValue([]),
  renameDocument: vi.fn(),
  renameChat: vi.fn(),
  getMemoryStatus: vi.fn().mockResolvedValue({ memory_consent_granted: false, fact_count: 0 }),
  fetchLabMetrics: vi.fn().mockResolvedValue([]),
  logout: vi.fn().mockResolvedValue({ message: 'ok' }),
  uploadPdfReport: vi.fn(),
  sendQueryStream: vi.fn(),
  deleteAccount: vi.fn(),
  updateProfile: vi.fn(),
  detachChatDocument: vi.fn(),
  getFacts: vi.fn().mockResolvedValue([]),
  createFact: vi.fn(),
  updateFact: vi.fn(),
  deleteFact: vi.fn(),
  updateMemoryConsent: vi.fn(),
  changePassword: vi.fn(),
  getMemoryFacts: vi.fn().mockResolvedValue([]),
  deleteMemoryFact: vi.fn(),
  clearAllMemoryFacts: vi.fn(),
}));

vi.mock('../services/speech', () => ({
  startSpeechRecognition: vi.fn(),
  speakText: vi.fn(),
  stopSpeaking: vi.fn(),
}));

function renderSidebar(overrides = {}) {
  const props = {
    isOpen: true,
    onToggle: vi.fn(),
    conversations: [
      { id: 'chat-1', title: 'Blood test results' },
      { id: 'chat-2', title: 'X-ray follow-up' },
    ],
    activeSessionId: 'chat-1',
    onSelectChat: vi.fn(),
    onNewChat: vi.fn(),
    onOpenSettings: vi.fn(),
    onOpenProfile: vi.fn(),
    darkMode: true,
    activePdf: null,
    onLogout: vi.fn(),
    onDeleteChat: vi.fn(),
    onRenameChat: vi.fn(),
    currentUser: { email: 'test@example.com' },
    ...overrides,
  };
  return { ...render(<Sidebar {...props} />), props };
}

function startRenameFirstChat() {
  fireEvent.click(screen.getAllByRole('button', { name: 'Chat options' })[0]);
  fireEvent.click(screen.getByRole('button', { name: /^rename$/i }));
  return screen.getByRole('textbox', { name: 'Rename chat' });
}

describe('Sidebar inline chat rename', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('replaces the title with an auto-focused, styled input inside the same chat item', () => {
    renderSidebar();

    // Title is shown before renaming.
    expect(screen.getByText('Blood test results')).toBeInTheDocument();

    const input = startRenameFirstChat();

    // The title span is REPLACED (not appended to) by the input.
    expect(screen.queryByText('Blood test results')).not.toBeInTheDocument();
    expect(input).toHaveValue('Blood test results');

    // Auto-focus is applied when edit mode is entered.
    expect(input).toHaveFocus();

    // Explicit dark-theme styling required by the fix (visible bg + border, flex-1).
    ['flex-1', 'bg-gray-800', 'text-white', 'px-2', 'py-1', 'rounded', 'border', 'border-gray-600'].forEach(
      (cls) => expect(input.className).toContain(cls)
    );
    expect(input.className).toContain('focus:outline-none');
    expect(input.className).toContain('focus:border-blue-500');

    // The edit row lives inside the chat item and the sibling item is untouched
    // (no push-down / overlap / removal).
    expect(input.parentElement.className).toContain('flex-1');
    expect(input.parentElement.className).toContain('items-center');
    expect(screen.getByText('X-ray follow-up')).toBeInTheDocument();
  });

  it('saves on Enter without asking the parent twice', () => {
    const { props } = renderSidebar();
    const input = startRenameFirstChat();

    fireEvent.change(input, { target: { value: 'Renamed by Enter' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(props.onRenameChat).toHaveBeenCalledTimes(1);
    expect(props.onRenameChat).toHaveBeenCalledWith('chat-1', 'Renamed by Enter');
    // Edit mode closes.
    expect(screen.queryByRole('textbox', { name: 'Rename chat' })).not.toBeInTheDocument();
  });

  it('saves via the confirm (✓) button', () => {
    const { props } = renderSidebar();
    const input = startRenameFirstChat();

    fireEvent.change(input, { target: { value: 'Renamed by check' } });
    fireEvent.click(screen.getByRole('button', { name: 'Confirm rename' }));

    expect(props.onRenameChat).toHaveBeenCalledWith('chat-1', 'Renamed by check');
    expect(screen.queryByRole('textbox', { name: 'Rename chat' })).not.toBeInTheDocument();
  });

  it('cancels via the ✗ button without saving', () => {
    const { props } = renderSidebar();
    const input = startRenameFirstChat();

    fireEvent.change(input, { target: { value: 'Should not be saved' } });
    fireEvent.click(screen.getByRole('button', { name: 'Cancel rename' }));

    expect(props.onRenameChat).not.toHaveBeenCalled();
    expect(screen.getByText('Blood test results')).toBeInTheDocument();
    expect(screen.queryByRole('textbox', { name: 'Rename chat' })).not.toBeInTheDocument();
  });

  it('cancels on Escape without saving', () => {
    const { props } = renderSidebar();
    const input = startRenameFirstChat();

    fireEvent.change(input, { target: { value: 'Should not be saved' } });
    fireEvent.keyDown(input, { key: 'Escape' });

    expect(props.onRenameChat).not.toHaveBeenCalled();
    expect(screen.getByText('Blood test results')).toBeInTheDocument();
  });

  it('does not save an empty/whitespace-only title', () => {
    const { props } = renderSidebar();
    const input = startRenameFirstChat();

    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    expect(props.onRenameChat).not.toHaveBeenCalled();
  });

  it('displays accurate toast when renaming a chat without a document', async () => {
    localStorage.clear();
    const noDocChat = { id: 'chat-nodoc', title: 'Consultation without report', messages: [] };
    localStorage.setItem('mediskye_session_id', 'chat-nodoc');
    localStorage.setItem('mediskye_last_active_user', 'u1');
    localStorage.setItem('mediskye_patient_id', 'self');
    localStorage.setItem('mediskye_conversations', JSON.stringify([noDocChat]));
    localStorage.setItem('mediskye_conversations_u1', JSON.stringify([noDocChat]));

    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // Open options on the chat and trigger rename
    const optionsBtn = await screen.findByRole('button', { name: 'Chat options' });
    fireEvent.click(optionsBtn);

    const renameBtn = screen.getByRole('button', { name: /^rename$/i });
    fireEvent.click(renameBtn);

    const input = screen.getByRole('textbox', { name: 'Rename chat' });
    fireEvent.change(input, { target: { value: 'Renamed general consultation' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    // Assert the accurate toast appears
    expect(
      await screen.findByText('Renamed locally (this chat has no server-side document)')
    ).toBeInTheDocument();
  });
});
