import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import React from 'react';

// ── Module mocks ──────────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  uploadPdfReport: vi.fn(),
  getUploadStatus: vi.fn(),
  sendQueryStream: vi.fn(),
  logout: vi.fn(),
  getProfile: vi.fn(),
  getDependents: vi.fn(),
  getUserDocuments: vi.fn(),
  getChatSessions: vi.fn().mockResolvedValue([]),
  getDocumentChats: vi.fn(),
  getGeneralChats: vi.fn().mockResolvedValue([]),
  renameDocument: vi.fn(),
  deleteDocument: vi.fn(),
  renameChatSession: vi.fn(),
  deleteChatSession: vi.fn().mockResolvedValue(true),
  clearAllChatSessions: vi.fn().mockResolvedValue(true),
  deleteAccount: vi.fn(),
  updateProfile: vi.fn(),
  detachChatDocument: vi.fn(),
  getDocumentSummary: vi.fn(),
  exportDocumentData: vi.fn(),
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
  userKey: vi.fn((prefix, uid) => `${prefix}_${uid || 'default'}`),
  getCurrentUid: vi.fn(() => 'u_test'),
  syncAllProfilesInBackground: vi.fn().mockResolvedValue({ success: true }),
  emitConnectivityStatus: vi.fn(),
  checkConnectivity: vi.fn().mockResolvedValue(true),
  API_BASE_URL: 'http://localhost:8000',
}));

vi.mock('../services/speech', () => ({
  speakText: vi.fn(),
  stopSpeaking: vi.fn(),
  startSpeechRecognition: vi.fn(),
  pickVoiceForLanguage: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

import * as api from '../services/api';
import * as speech from '../services/speech';
import ChatApp from '../components/ChatApp';

async function sendMessage(text) {
  const input = screen.getByPlaceholderText(/Ask a medical question/i);
  await act(async () => {
    fireEvent.change(input, { target: { value: text } });
    fireEvent.submit(input.closest('form'));
  });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();

  api.getProfile.mockResolvedValue({ id: 'user-1', email: 'test@example.com', memory_consent_granted: true });
  api.getDependents.mockResolvedValue([]);
  api.getUserDocuments.mockResolvedValue([]);
  api.getDocumentChats.mockResolvedValue([]);
  api.getDocumentSummary.mockResolvedValue({ summary: '', cached: true });
  api.sendQueryStream.mockImplementation((_q, _docId, _lang, onChunk) => {
    onChunk({ chunk: 'Your hemoglobin ' });
    onChunk({ chunk: 'is normal.' });
    return Promise.resolve();
  });
  speech.speakText.mockImplementation(() => 1);
});

describe('ChatApp — auto-read AI responses aloud', () => {
  it('speaks the completed answer when auto-read is enabled', async () => {
    localStorage.setItem('mediskye_auto_read', 'true');
    render(<ChatApp />);

    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await sendMessage('What is my hemoglobin?');

    await waitFor(() => expect(speech.speakText).toHaveBeenCalled());
    expect(speech.speakText).toHaveBeenCalledWith('Your hemoglobin is normal.', undefined, 'English');
  });

  it('does not speak when auto-read is disabled', async () => {
    render(<ChatApp />);

    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await sendMessage('What is my hemoglobin?');

    // Stream completes; give any (wrong) auto-read a chance to fire.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });
    expect(speech.speakText).not.toHaveBeenCalled();
  });

  it('silences any ongoing speech when a new question is sent', async () => {
    localStorage.setItem('mediskye_auto_read', 'true');
    render(<ChatApp />);

    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await sendMessage('What is my hemoglobin?');

    expect(speech.stopSpeaking).toHaveBeenCalled();
  });

  it('does not speak when the stream reports an error', async () => {
    localStorage.setItem('mediskye_auto_read', 'true');
    api.sendQueryStream.mockImplementation((_q, _docId, _lang, onChunk) => {
      onChunk({ chunk: 'Partial answer' });
      onChunk({ error: 'Generation failed' });
      return Promise.resolve();
    });
    render(<ChatApp />);

    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await sendMessage('What is my hemoglobin?');

    await act(async () => {
      await new Promise((r) => setTimeout(r, 100));
    });
    expect(speech.speakText).not.toHaveBeenCalled();
  });
});
