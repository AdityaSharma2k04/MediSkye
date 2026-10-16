import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import ChatApp from '../components/ChatApp';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  uploadPdfReport: vi.fn(),
  sendQueryStream: vi.fn(),
  logout: vi.fn().mockResolvedValue({ message: 'ok' }),
  getProfile: vi.fn(),
  getDependents: vi.fn(),
  getUserDocuments: vi.fn(),
  getDocumentChats: vi.fn(),
  renameChat: vi.fn(),
  renameDocument: vi.fn(),
  deleteAccount: vi.fn(),
  updateProfile: vi.fn(),
  detachChatDocument: vi.fn(),
  fetchLabMetrics: vi.fn(),
  // Pulled in transitively by SettingsModal -> HealthProfile
  getFacts: vi.fn(),
  createFact: vi.fn(),
  updateFact: vi.fn(),
  deleteFact: vi.fn(),
  // SettingsModal
  getMemoryStatus: vi.fn(),
  updateMemoryConsent: vi.fn(),
  changePassword: vi.fn(),
  getMemoryFacts: vi.fn(),
  deleteMemoryFact: vi.fn(),
  clearAllMemoryFacts: vi.fn(),
}));

vi.mock('../services/speech', () => ({
  startSpeechRecognition: vi.fn(),
  speakText: vi.fn(),
  stopSpeaking: vi.fn(),
}));

function seedConversation(conv) {
  localStorage.setItem('mediskye_session_id', conv.id);
  localStorage.setItem('mediskye_last_active_user', 'u1');
  localStorage.setItem('mediskye_patient_id', 'self');
  localStorage.setItem('mediskye_conversations', JSON.stringify([conv]));
  localStorage.setItem('mediskye_conversations_u1', JSON.stringify([conv]));
}

function renderApp() {
  return render(
    <MemoryRouter>
      <ChatApp />
    </MemoryRouter>
  );
}

describe('ChatApp bug fixes', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();

    api.getProfile.mockResolvedValue({
      id: 'u1',
      email: 'u@test.com',
      full_name: 'Test User',
      memory_consent_granted: true,
      language_preference: 'English',
    });
    api.getDependents.mockResolvedValue([]);
    api.getUserDocuments.mockResolvedValue([]);
    api.getDocumentChats.mockResolvedValue([]);
    api.detachChatDocument.mockResolvedValue({ message: 'detached' });
    api.fetchLabMetrics.mockResolvedValue([]);
    api.getFacts.mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
  });

  it('F2: regenerate replaces the assistant reply without duplicating the user message', async () => {
    seedConversation({
      id: 'chat-1',
      title: 'Test Chat',
      messages: [
        { id: 1, sender: 'user', text: 'What is hemoglobin?', timestamp: '10:00' },
        { id: 2, sender: 'assistant', text: 'Old answer', timestamp: '10:01' },
      ],
      pdf: null,
      documents: [],
    });

    api.sendQueryStream.mockImplementation(async (q, docId, lang, onChunk) => {
      if (onChunk) onChunk({ chunk: 'New answer' });
    });

    renderApp();

    await screen.findAllByText('Old answer');
    // The question is rendered twice (visible bubble + hidden print summary).
    const beforeCount = screen.getAllByText('What is hemoglobin?').length;

    fireEvent.click(screen.getByTitle('Regenerate AI response'));

    await waitFor(() => expect(api.sendQueryStream).toHaveBeenCalledTimes(1));
    expect(api.sendQueryStream.mock.calls[0][0]).toBe('What is hemoglobin?');

    await waitFor(() => expect(screen.getAllByText('New answer').length).toBeGreaterThan(0));
    await waitFor(() => expect(screen.queryAllByText('Old answer')).toHaveLength(0));

    // No duplicate user bubble was appended.
    expect(screen.getAllByText('What is hemoglobin?')).toHaveLength(beforeCount);
  });

  it('F4: clicking Stop aborts the in-flight streaming request', async () => {
    seedConversation({
      id: 'chat-1',
      title: 'Test Chat',
      messages: [],
      pdf: null,
      documents: [],
    });

    let capturedSignal = null;
    api.sendQueryStream.mockImplementation((q, docId, lang, onChunk, patientId, signal) => {
      capturedSignal = signal;
      return new Promise((resolve, reject) => {
        if (signal) {
          signal.addEventListener('abort', () => {
            const err = new Error('aborted');
            err.name = 'AbortError';
            reject(err);
          });
        }
      });
    });

    renderApp();

    const textarea = await screen.findByPlaceholderText(
      'Ask a medical question about your report...'
    );
    fireEvent.change(textarea, { target: { value: 'Hello doctor' } });
    fireEvent.click(screen.getByTitle('Send message'));

    const stopBtn = await screen.findByTitle('Stop generation');
    await waitFor(() => expect(api.sendQueryStream).toHaveBeenCalledTimes(1));
    expect(capturedSignal).toBeTruthy();
    expect(capturedSignal.aborted).toBe(false);

    fireEvent.click(stopBtn);

    await waitFor(() => expect(capturedSignal.aborted).toBe(true));
    // Once generation stops, the send button is restored.
    await screen.findByTitle('Send message');
  });

  it('F3: detaching a document keeps the remaining reports and updates state', async () => {
    seedConversation({
      id: 'chat-1',
      title: 'Test Chat',
      messages: [{ id: 1, sender: 'user', text: 'Summarize', timestamp: '10:00' }],
      pdf: { name: 'first.pdf' },
      document_id: 'd1',
      documents: [
        { id: 'd1', name: 'first.pdf', filename: 'first.pdf' },
        { id: 'd2', name: 'second.pdf', filename: 'second.pdf' },
      ],
    });

    renderApp();

    fireEvent.click(await screen.findByLabelText('Detach first.pdf'));

    await waitFor(() => {
      expect(api.detachChatDocument).toHaveBeenCalledWith('chat-1', 'd1');
    });
    await waitFor(() => {
      expect(screen.queryByLabelText('Detach first.pdf')).not.toBeInTheDocument();
    });
    expect(screen.getByLabelText('Detach second.pdf')).toBeInTheDocument();
  });
});
