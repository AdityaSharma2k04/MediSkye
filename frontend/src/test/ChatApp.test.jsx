import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import React from 'react';

// ── Module mocks (must be declared before imports that use them) ──────────────
vi.mock('../services/api', () => ({
  uploadPdfReport: vi.fn(),
  sendQueryStream: vi.fn(),
  logout: vi.fn(),
  getProfile: vi.fn(),
  getDependents: vi.fn(),
  getUserDocuments: vi.fn(),
  getDocumentChats: vi.fn(),
  renameDocument: vi.fn(),
  deleteAccount: vi.fn(),
  updateProfile: vi.fn(),
  detachChatDocument: vi.fn(),
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

import * as api from '../services/api';
import ChatApp from '../components/ChatApp';

// ── Helpers ───────────────────────────────────────────────────────────────────
const SERVER_DOC_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

function makeFile(name = 'blood_test.pdf', type = 'application/pdf') {
  return new File(['%PDF-1.4 content'], name, { type });
}

beforeEach(() => {
  vi.clearAllMocks();
  localStorage.clear();

  api.getProfile.mockResolvedValue({ id: 'user-1', email: 'test@example.com', memory_consent_granted: true });
  api.getDependents.mockResolvedValue([]);
  api.getUserDocuments.mockResolvedValue([]);
  api.getDocumentChats.mockResolvedValue([]);
  api.uploadPdfReport.mockResolvedValue({
    message: 'PDF uploaded and processed successfully.',
    document_id: SERVER_DOC_ID,
  });
});

describe('ChatApp — upload refreshes sidebar immediately', () => {
  it('promotes conversation id to server document_id after upload', async () => {
    render(<ChatApp />);

    // Wait for profile/deps and initial document check to load
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalled());

    // Simulate file attach via the internal handleAttachFile
    // We reach it through the ChatInput's file input
    const fileInput = document.querySelector('input[type="file"]');
    expect(fileInput).not.toBeNull();

    const file = makeFile();
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    await waitFor(() => expect(api.uploadPdfReport).toHaveBeenCalledTimes(1));
    expect(api.uploadPdfReport).toHaveBeenCalledWith(
      file,
      'self',
      expect.any(String), // sessionId (client-generated UUID)
    );

    // After upload the session id in localStorage must equal the server doc id
    await waitFor(() => {
      expect(localStorage.getItem('mediskye_session_id')).toBe(SERVER_DOC_ID);
    });

    // The conversations array stored in localStorage must contain an entry
    // whose id matches the server document_id — wait for the sync effect
    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem('mediskye_conversations') || '[]');
      const match = stored.find((c) => c.id === SERVER_DOC_ID);
      expect(match).toBeDefined();
      expect(match.document_id).toBe(SERVER_DOC_ID);
    });
  });

  it('shows success toast and does NOT require re-login to see the document', async () => {
    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    const fileInput = document.querySelector('input[type="file"]');
    const file = makeFile();

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    await waitFor(() => expect(api.uploadPdfReport).toHaveBeenCalled());

    // Success toast text should appear in the DOM
    await waitFor(() => {
      expect(screen.getByText('Report Processed')).toBeInTheDocument();
    });
  });

  it('rejects non-PDF/image files before calling uploadPdfReport', async () => {
    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    const fileInput = document.querySelector('input[type="file"]');
    const badFile = new File(['data'], 'malware.exe', { type: 'application/octet-stream' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [badFile] } });
    });

    expect(api.uploadPdfReport).not.toHaveBeenCalled();
    await waitFor(() => {
      expect(screen.getByText('Invalid File Format')).toBeInTheDocument();
    });
  });

  it('accepts image files (jpg/png) and calls uploadPdfReport', async () => {
    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    const fileInput = document.querySelector('input[type="file"]');
    const imgFile = makeFile('xray.jpg', 'image/jpeg');

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [imgFile] } });
    });

    await waitFor(() => expect(api.uploadPdfReport).toHaveBeenCalledTimes(1));
    expect(api.uploadPdfReport).toHaveBeenCalledWith(imgFile, 'self', expect.any(String));
  });

  it('refetches documents and updates state when upload succeeds', async () => {
    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(1));

    api.getUserDocuments.mockResolvedValueOnce([
      {
        id: SERVER_DOC_ID,
        filename: 'blood_test.pdf',
        file_path: '/indexes/doc.index',
        title: 'Blood Test Report',
        created_at: new Date().toISOString(),
      },
    ]);

    const fileInput = document.querySelector('input[type="file"]');
    const file = makeFile();

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    await waitFor(() => expect(api.uploadPdfReport).toHaveBeenCalledTimes(1));
    // Assert getUserDocuments is called again after upload
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(2));

    // Assert the new document is registered in conversations
    await waitFor(() => {
      const stored = JSON.parse(localStorage.getItem('mediskye_conversations') || '[]');
      expect(stored.some((c) => c.id === SERVER_DOC_ID)).toBe(true);
    });
  });
});
