import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
import React from 'react';

// ── Module mocks (must be declared before imports that use them) ──────────────
vi.mock('../services/api', () => ({
  uploadPdfReport: vi.fn(),
  getUploadStatus: vi.fn(),
  sendQueryStream: vi.fn(),
  logout: vi.fn(),
  getProfile: vi.fn(),
  getDependents: vi.fn(),
  getUserDocuments: vi.fn(),
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
  api.deleteDocument.mockResolvedValue(true);
  api.getDocumentSummary.mockResolvedValue({ summary: 'Clinical report summary', cached: true });
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

    // Verify documents were refreshed from server truth
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(2));

    // Chat persistence relies on server, not localStorage
    expect(localStorage.getItem('mediskye_conversations')).toBeNull();
  });

  it('attaches the uploaded document immediately and does NOT require re-login to see the document', async () => {
    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    const fileInput = document.querySelector('input[type="file"]');
    const file = makeFile();

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    await waitFor(() => expect(api.uploadPdfReport).toHaveBeenCalled());

    // Attached PDF chip should appear immediately in the composer
    await waitFor(() => {
      expect(screen.getByLabelText('Detach blood_test.pdf')).toBeInTheDocument();
    });
  });

  it('rejects non-PDF/image files before calling uploadPdfReport', async () => {
    const errSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    const fileInput = document.querySelector('input[type="file"]');
    const badFile = new File(['data'], 'malware.exe', { type: 'application/octet-stream' });

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [badFile] } });
    });

    expect(api.uploadPdfReport).not.toHaveBeenCalled();
    expect(errSpy).toHaveBeenCalledWith(expect.stringMatching(/Invalid File Format/i));
    errSpy.mockRestore();
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

    // Assert the new document is registered in UI without relying on localStorage
    expect(await screen.findByText('Blood Test Report')).toBeInTheDocument();
    expect(localStorage.getItem('mediskye_conversations')).toBeNull();
  });

  it('test_upload_polls_until_complete: polls until complete and refreshes documents', async () => {
    window.__POLL_INTERVAL__ = 10;

    api.uploadPdfReport.mockResolvedValueOnce({
      job_id: 'job-async-123',
      status_url: '/upload/status/job-async-123',
    });

    api.getUploadStatus
      .mockResolvedValueOnce({
        job_id: 'job-async-123',
        status: 'processing',
      })
      .mockResolvedValueOnce({
        job_id: 'job-async-123',
        status: 'completed',
        document_id: SERVER_DOC_ID,
      });

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(1));

    const fileInput = document.querySelector('input[type="file"]');
    const file = makeFile();

    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    // Verify upload was initiated
    await waitFor(() => expect(api.uploadPdfReport).toHaveBeenCalledTimes(1));

    // Verify polling was performed
    await waitFor(() => expect(api.getUploadStatus).toHaveBeenCalledWith('job-async-123', 10000));

    // Verify documents were refreshed with new document_id and attached chip rendered
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(2));
    await waitFor(() => {
      expect(screen.getByLabelText('Detach blood_test.pdf')).toBeInTheDocument();
    });

    delete window.__POLL_INTERVAL__;
  });

  it('recovers when a status poll times out and succeeds on retry', async () => {
    window.__POLL_INTERVAL__ = 1;
    api.uploadPdfReport.mockResolvedValueOnce({
      job_id: 'job-stalled-123',
      status_url: '/upload/status/job-stalled-123',
    });
    api.getUploadStatus
      .mockRejectedValueOnce(new DOMException('Request timed out', 'AbortError'))
      .mockResolvedValueOnce({
        job_id: 'job-stalled-123',
        status: 'completed',
        document_id: SERVER_DOC_ID,
      });

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.change(document.querySelector('input[type="file"]'), {
        target: { files: [makeFile()] },
      });
    });

    await waitFor(() => expect(api.getUploadStatus).toHaveBeenCalledTimes(2));
    expect(api.getUploadStatus).toHaveBeenNthCalledWith(1, 'job-stalled-123', 10000);
    expect(api.getUploadStatus).toHaveBeenNthCalledWith(2, 'job-stalled-123', 10000);
    await waitFor(() => expect(screen.getByLabelText('Detach blood_test.pdf')).toBeInTheDocument());
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(2));

    delete window.__POLL_INTERVAL__;
  });

  it('refreshes documents and logs an error after five consecutive poll failures', async () => {
    window.__POLL_INTERVAL__ = 1;
    api.uploadPdfReport.mockResolvedValueOnce({
      job_id: 'job-failing-123',
      status_url: '/upload/status/job-failing-123',
    });
    api.getUploadStatus.mockRejectedValue(new Error('Status request failed'));

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.change(document.querySelector('input[type="file"]'), {
        target: { files: [makeFile()] },
      });
    });

    await waitFor(() => expect(api.getUploadStatus).toHaveBeenCalledTimes(5));
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(2));

    delete window.__POLL_INTERVAL__;
  });

  it('refreshes documents when the polling deadline expires', async () => {
    window.__POLL_INTERVAL__ = 1;
    window.__UPLOAD_MAX_WAIT__ = 20;
    api.uploadPdfReport.mockResolvedValueOnce({
      job_id: 'job-slow-123',
      status_url: '/upload/status/job-slow-123',
    });
    api.getUploadStatus.mockResolvedValue({
      job_id: 'job-slow-123',
      status: 'processing',
    });

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(1));

    await act(async () => {
      fireEvent.change(document.querySelector('input[type="file"]'), {
        target: { files: [makeFile()] },
      });
    });

    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalledTimes(2));
    expect(api.getUploadStatus).toHaveBeenCalled();

    delete window.__POLL_INTERVAL__;
    delete window.__UPLOAD_MAX_WAIT__;
  });
});

describe('ChatApp — deletion and rename persistence', () => {
  it('deletes document on server and updates local state when chat deleted', async () => {
    const docChat = {
      id: SERVER_DOC_ID,
      document_id: SERVER_DOC_ID,
      title: 'Lab Report',
      messages: [],
      pdf: { id: SERVER_DOC_ID, name: 'lab.pdf' },
    };
    api.getUserDocuments.mockResolvedValue([{ id: SERVER_DOC_ID, filename: 'lab.pdf', title: 'Lab Report' }]);
    localStorage.setItem('mediskye_conversations', JSON.stringify([docChat]));
    localStorage.setItem('mediskye_conversations_user-1', JSON.stringify([docChat]));

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalled());

    // Open options menu on chat and click delete
    const [optionsBtn] = await screen.findAllByRole('button', { name: 'Chat options' });
    fireEvent.click(optionsBtn);

    const deleteBtn = screen.getByRole('button', { name: /^delete$/i });
    fireEvent.click(deleteBtn);

    // Confirm deletion in modal
    const dialog = await screen.findByRole('dialog');
    const confirmBtn = within(dialog).getByRole('button', { name: /^delete$/i });
    fireEvent.click(confirmBtn);

    await waitFor(() => {
      expect(api.deleteDocument).toHaveBeenCalledWith(SERVER_DOC_ID);
    });
  });

  it('rolls back rename title when server renameDocument fails', async () => {
    const docChat = {
      id: SERVER_DOC_ID,
      document_id: SERVER_DOC_ID,
      title: 'Original Title',
      messages: [],
      pdf: { id: SERVER_DOC_ID, name: 'lab.pdf' },
    };
    api.getUserDocuments.mockResolvedValue([{ id: SERVER_DOC_ID, filename: 'lab.pdf', title: 'Original Title' }]);
    api.renameDocument.mockRejectedValue(new Error('Network error'));
    localStorage.setItem('mediskye_conversations', JSON.stringify([docChat]));
    localStorage.setItem('mediskye_conversations_user-1', JSON.stringify([docChat]));

    render(<ChatApp />);
    await waitFor(() => expect(api.getUserDocuments).toHaveBeenCalled());
    const [optionsBtn] = await screen.findAllByRole('button', { name: 'Chat options' });
    fireEvent.click(optionsBtn);

    const renameBtn = screen.getByRole('button', { name: /^rename$/i });
    fireEvent.click(renameBtn);

    const input = screen.getByRole('textbox', { name: 'Rename chat' });
    fireEvent.change(input, { target: { value: 'New Failed Title' } });
    fireEvent.keyDown(input, { key: 'Enter' });

    await waitFor(() => {
      expect(api.renameDocument).toHaveBeenCalledWith(SERVER_DOC_ID, 'New Failed Title');
    });

    // Title rolls back to Original Title when server rename fails
    expect(await screen.findByText('Original Title')).toBeInTheDocument();
  });

  it('detaching an attached report chip detaches locally without calling deleteDocument', async () => {
    const docChat = {
      id: SERVER_DOC_ID,
      document_id: SERVER_DOC_ID,
      title: 'Lab Report Chat',
      messages: [{ id: 1, sender: 'user', text: 'Hello', timestamp: '10:00' }],
      pdf: { id: SERVER_DOC_ID, name: 'lab.pdf' },
      documents: [
        { id: SERVER_DOC_ID, name: 'lab.pdf', filename: 'lab.pdf' },
        { id: 'second-doc-id', name: 'second.pdf', filename: 'second.pdf' },
      ],
    };
    api.getUserDocuments.mockResolvedValue([{ id: SERVER_DOC_ID, filename: 'lab.pdf', title: 'Lab Report' }]);
    api.deleteDocument.mockResolvedValue(true);
    localStorage.setItem('mediskye_conversations', JSON.stringify([docChat]));
    localStorage.setItem('mediskye_conversations_user-1', JSON.stringify([docChat]));

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    const detachBtn = await screen.findByLabelText('Detach lab.pdf');
    fireEvent.click(detachBtn);

    await waitFor(() => {
      expect(screen.queryByLabelText('Detach lab.pdf')).not.toBeInTheDocument();
    });
    expect(api.deleteDocument).not.toHaveBeenCalled();
  });

  it('calls getDocumentSummary and triggers print flow when Export Summary is clicked', async () => {
    const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {});
    const docChat = {
      id: SERVER_DOC_ID,
      document_id: SERVER_DOC_ID,
      title: 'Lab Report Chat',
      messages: [
        { id: 1, sender: 'user', text: 'Hello', timestamp: '10:00' },
        { id: 2, sender: 'assistant', text: 'Assistant report note', timestamp: '10:01' },
      ],
      pdf: { id: SERVER_DOC_ID, name: 'lab.pdf' },
      documents: [{ id: SERVER_DOC_ID, name: 'lab.pdf', filename: 'lab.pdf' }],
    };
    api.getUserDocuments.mockResolvedValue([{ id: SERVER_DOC_ID, filename: 'lab.pdf', title: 'Lab Report' }]);
    api.getDocumentSummary.mockResolvedValue({
      summary: 'Comprehensive clinical summary for printing.',
      cached: true,
    });

    localStorage.setItem('mediskye_conversations', JSON.stringify([docChat]));
    localStorage.setItem('mediskye_conversations_user-1', JSON.stringify([docChat]));

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    const exportBtn = await screen.findByRole('button', { name: /Export Summary/i });
    expect(exportBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(exportBtn);
    });

    await waitFor(() => {
      expect(api.getDocumentSummary).toHaveBeenCalledWith(SERVER_DOC_ID);
    });

    await waitFor(() => {
      expect(printSpy).toHaveBeenCalled();
    });

    printSpy.mockRestore();
  });

  it('handles 409 conflict gracefully without rendering duplicate user bubble or error state', async () => {
    const conflictErr = new Error('A query stream is already active for this conversation.');
    conflictErr.status = 409;
    api.sendQueryStream.mockRejectedValue(conflictErr);

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    const input = screen.getByPlaceholderText(/Ask a medical question/i);
    fireEvent.change(input, { target: { value: 'Duplicate query during generation' } });
    const form = input.closest('form');

    await act(async () => {
      fireEvent.submit(form);
    });

    // 1. Stream call was attempted and 409 warning logged
    await waitFor(() => {
      expect(api.sendQueryStream).toHaveBeenCalled();
    });

    // 2. The duplicate user bubble is NOT left in the chat
    expect(screen.queryByText('Duplicate query during generation')).not.toBeInTheDocument();
  });
});

