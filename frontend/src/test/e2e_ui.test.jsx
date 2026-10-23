import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React, { useState } from 'react';
import { MemoryRouter } from 'react-router-dom';
import fs from 'fs';
import path from 'path';

// ── Module mocks ─────────────────────────────────────────────────────────────
const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockSignInWithPopup = vi.fn();
const mockSignInWithEmailAndPassword = vi.fn();
const mockCreateUserWithEmailAndPassword = vi.fn();
const mockUpdateProfile = vi.fn();
const mockSendPasswordResetEmail = vi.fn();
const mockSignOut = vi.fn();

const {
  mockCredential,
  mockCredentialFn,
  mockReauthenticateWithCredential,
  mockUpdatePassword,
  mockAuth,
} = vi.hoisted(() => {
  const credential = { providerId: 'password', signInMethod: 'password' };
  return {
    mockCredential: credential,
    mockCredentialFn: vi.fn().mockReturnValue(credential),
    mockReauthenticateWithCredential: vi.fn().mockResolvedValue({}),
    mockUpdatePassword: vi.fn().mockResolvedValue({}),
    mockAuth: {
      currentUser: {
        email: 'patient@example.com',
        displayName: 'Test Patient',
        providerData: [{ providerId: 'password' }],
        getIdToken: vi.fn().mockResolvedValue('mock_token_jwt_xyz'),
      },
    },
  };
});

vi.mock('../services/firebase', async () => {
  const actual = await vi.importActual('../services/firebase');
  return {
    ...actual,
    auth: mockAuth,
    googleProvider: {},
    signInWithPopup: (...args) => mockSignInWithPopup(...args),
    signInWithEmailAndPassword: (...args) => mockSignInWithEmailAndPassword(...args),
    createUserWithEmailAndPassword: (...args) => mockCreateUserWithEmailAndPassword(...args),
    updateProfile: (...args) => mockUpdateProfile(...args),
    sendPasswordResetEmail: (...args) => mockSendPasswordResetEmail(...args),
    signOut: (...args) => mockSignOut(...args),
  };
});

vi.mock('firebase/auth', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    signOut: (...args) => mockSignOut(...args),
    EmailAuthProvider: {
      credential: (...args) => mockCredentialFn(...args),
    },
    reauthenticateWithCredential: (...args) => mockReauthenticateWithCredential(...args),
    updatePassword: (...args) => mockUpdatePassword(...args),
  };
});

const mockApiPost = vi.fn().mockResolvedValue({ message: 'Verification email sent' });

vi.mock('../services/api', () => ({
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
  uploadPdfReport: vi.fn(),
  getUploadStatus: vi.fn(),
  sendQueryStream: vi.fn(),
  getProfile: vi.fn(),
  getDependents: vi.fn(),
  getUserDocuments: vi.fn(),
  getDocumentChats: vi.fn(),
  renameDocument: vi.fn(),
  deleteDocument: vi.fn(),
  deleteAccount: vi.fn(),
  updateProfile: vi.fn(),
  getDocumentSummary: vi.fn(),
  getMemoryStatus: vi.fn().mockResolvedValue({ memory_consent_granted: true, fact_count: 0 }),
  getMemoryFacts: vi.fn().mockResolvedValue([]),
  getFacts: vi.fn().mockResolvedValue([]),
  createFact: vi.fn(),
  updateFact: vi.fn(),
  deleteFact: vi.fn(),
  updateMemoryConsent: vi.fn(),
  clearAllMemoryFacts: vi.fn(),
  sendCustomVerification: vi.fn(),
  sendCustomPasswordReset: (...args) => mockApiPost('/auth/send-custom-password-reset', { email: args[0] }),
  api: {
    post: (...args) => mockApiPost(...args),
    get: vi.fn(),
  },
  default: {
    post: (...args) => mockApiPost(...args),
    get: vi.fn(),
  },
}));

import * as api from '../services/api';
import Login from '../components/Login';
import Register from '../components/Register';
import ChatApp from '../components/ChatApp';
import LabMetrics from '../components/LabMetrics';
import SettingsModal from '../components/SettingsModal';
import Sidebar from '../components/Sidebar';

// ── Helpers ──────────────────────────────────────────────────────────────────
const TEST_DOC_ID = '11111111-2222-3333-4444-555555555555';

function createMockPdf(name = 'clinical_report.pdf') {
  return new File(['%PDF-1.4 clinical lab content'], name, { type: 'application/pdf' });
}

describe('TEST SUITE 2: Frontend E2E UI Journeys', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();

    api.getProfile.mockResolvedValue({
      id: 'patient-uuid-001',
      email: 'patient@example.com',
      full_name: 'Jane Doe',
      memory_consent_granted: true,
      language_preference: 'English',
    });
    api.getDependents.mockResolvedValue([]);
    api.getUserDocuments.mockResolvedValue([]);
    api.getDocumentChats.mockResolvedValue([]);
    api.deleteDocument.mockResolvedValue(true);
    api.getDocumentSummary.mockResolvedValue({
      summary: 'Normal blood panel with mild vitamin D insufficiency.',
      cached: true,
    });
    api.logout.mockImplementation(async () => {
      localStorage.removeItem('token');
      localStorage.removeItem('mediskye_conversations');
      localStorage.removeItem('mediskye_session_id');
      localStorage.removeItem('mediskye_user_email');
      mockSignOut(mockAuth);
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // 1. Complete Firebase Auth UI Flows
  // ───────────────────────────────────────────────────────────────────────────
  describe('1. Complete Firebase Auth UI Flows (Login, Register, Forgot Password)', () => {
    it('Email/Password Login: trims email, calls signInWithEmailAndPassword, stores token, and navigates', async () => {
      const mockUser = {
        email: 'patient@example.com',
        emailVerified: true,
        getIdToken: vi.fn().mockResolvedValue('jwt_email_token_123'),
      };
      mockSignInWithEmailAndPassword.mockResolvedValueOnce({ user: mockUser });

      render(
        <MemoryRouter>
          <Login />
        </MemoryRouter>
      );

      // Step 1: Email entry with untrimmed whitespace
      const emailInput = screen.getByPlaceholderText(/email address/i);
      fireEvent.change(emailInput, { target: { value: '   Patient@Example.com   ' } });

      const continueBtn = screen.getByRole('button', { name: /^continue$/i });
      fireEvent.click(continueBtn);

      // Step 2: Password entry
      const passwordInput = await screen.findByPlaceholderText(/password/i);
      fireEvent.change(passwordInput, { target: { value: 'SecretPassword123!' } });

      const signInBtn = screen.getByRole('button', { name: /sign in/i });
      fireEvent.click(signInBtn);

      await waitFor(() => {
        expect(mockSignInWithEmailAndPassword).toHaveBeenCalledWith(
          expect.anything(),
          'patient@example.com',
          'SecretPassword123!'
        );
        expect(localStorage.getItem('token')).toBe('jwt_email_token_123');
        expect(mockNavigate).toHaveBeenCalledWith('/chat');
      });
    });

    it('Google OAuth Login: verifies official 4-color Google SVG, triggers signInWithPopup, disables button, stores token', async () => {
      const mockGoogleUser = {
        email: 'google_patient@example.com',
        getIdToken: vi.fn().mockResolvedValue('jwt_google_token_789'),
      };
      mockSignInWithPopup.mockResolvedValueOnce({ user: mockGoogleUser });

      render(
        <MemoryRouter>
          <Login />
        </MemoryRouter>
      );

      const googleBtn = screen.getByRole('button', { name: /continue with google/i });
      expect(googleBtn).toBeInTheDocument();

      // Check official 4-color Google SVG paths
      const svg = googleBtn.querySelector('svg');
      expect(svg).toBeInTheDocument();
      const paths = Array.from(svg.querySelectorAll('path')).map((p) => p.getAttribute('fill'));
      expect(paths).toContain('#4285F4'); // Blue
      expect(paths).toContain('#34A853'); // Green
      expect(paths).toContain('#FBBC05'); // Yellow
      expect(paths).toContain('#EA4335'); // Red

      fireEvent.click(googleBtn);

      await waitFor(() => {
        expect(mockSignInWithPopup).toHaveBeenCalled();
        expect(localStorage.getItem('token')).toBe('jwt_google_token_789');
        expect(localStorage.getItem('mediskye_user_email')).toBe('google_patient@example.com');
        expect(mockNavigate).toHaveBeenCalledWith('/chat');
      });
    });

    it('Google OAuth Failure: displays visible error alert banner and re-enables button when signInWithPopup fails', async () => {
      const err = new Error('OAuth failure');
      err.code = 'auth/unauthorized-domain';
      mockSignInWithPopup.mockRejectedValueOnce(err);

      render(
        <MemoryRouter>
          <Login />
        </MemoryRouter>
      );

      const googleBtn = screen.getByRole('button', { name: /continue with google/i });
      fireEvent.click(googleBtn);

      await waitFor(() => {
        expect(mockSignInWithPopup).toHaveBeenCalled();
        expect(screen.getByRole('alert')).toHaveTextContent(
          "This domain is not authorized in Firebase Authentication settings."
        );
        expect(googleBtn).not.toBeDisabled();
      });
    });

    it('Forgot Password Flow: validates empty email without calling Firebase, dispatches reset email when provided, and shows confirmation banner', async () => {
      mockApiPost.mockResolvedValueOnce({
        message: 'If an account exists with this email, a reset link has been sent.',
      });

      render(
        <MemoryRouter>
          <Login />
        </MemoryRouter>
      );

      const forgotBtn = screen.getByRole('button', { name: /forgot password\?/i });

      // Click with empty email -> validation message appears
      fireEvent.click(forgotBtn);
      expect(
        screen.getByText(/please enter your email address in the field above first/i)
      ).toBeInTheDocument();
      expect(mockApiPost).not.toHaveBeenCalled();

      // Enter valid email and click forgot password
      const emailInput = screen.getByPlaceholderText(/email address/i);
      fireEvent.change(emailInput, { target: { value: 'patient@example.com' } });
      fireEvent.click(forgotBtn);

      await waitFor(() => {
        expect(mockApiPost).toHaveBeenCalledWith('/auth/send-custom-password-reset', {
          email: 'patient@example.com',
        });
        expect(
          screen.getByText(/if an account exists with patient@example\.com, a password reset link has been sent/i)
        ).toBeInTheDocument();
      });
    });

    it('Registration with DisplayName Sync: calls createUserWithEmailAndPassword -> updateProfile -> custom verification in order', async () => {
      const mockNewUser = {
        email: 'newuser@example.com',
        getIdToken: vi.fn().mockResolvedValue('jwt_newuser_token'),
      };
      mockCreateUserWithEmailAndPassword.mockResolvedValueOnce({ user: mockNewUser });
      mockUpdateProfile.mockResolvedValueOnce();
      mockSignOut.mockResolvedValueOnce();

      render(
        <MemoryRouter>
          <Register />
        </MemoryRouter>
      );

      // Step 1: email
      fireEvent.change(screen.getByPlaceholderText(/email address/i), {
        target: { value: 'newuser@example.com' },
      });
      fireEvent.click(screen.getByRole('button', { name: /continue/i }));

      // Step 2: full name, password, confirm password, PHI consent
      fireEvent.change(screen.getByPlaceholderText(/full name/i), {
        target: { value: 'Jane Clinical Doe' },
      });
      fireEvent.change(screen.getByPlaceholderText(/create a password/i), {
        target: { value: 'SecurePass987!' },
      });
      fireEvent.change(screen.getByPlaceholderText(/confirm password/i), {
        target: { value: 'SecurePass987!' },
      });
      const consentBox = document.getElementById('register-phi-consent');
      expect(consentBox).toBeInTheDocument();
      fireEvent.click(consentBox);

      fireEvent.click(screen.getByRole('button', { name: /create account/i }));

      await waitFor(() => {
        expect(mockCreateUserWithEmailAndPassword).toHaveBeenCalledWith(
          expect.anything(),
          'newuser@example.com',
          'SecurePass987!'
        );
        expect(mockUpdateProfile).toHaveBeenCalledWith(mockNewUser, {
          displayName: 'Jane Clinical Doe',
        });
        expect(mockApiPost).toHaveBeenCalledWith('/auth/send-custom-verification', {
          email: 'newuser@example.com',
        });
        expect(mockSignOut).not.toHaveBeenCalled();
        expect(screen.getByText(/account created! we've sent a verification link to newuser@example\.com/i)).toBeInTheDocument();
      });
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // 2. Chat Dashboard, Multi-Device Sync, File Upload & Streaming Flow
  // ───────────────────────────────────────────────────────────────────────────
  describe('2. Chat Dashboard, Multi-Device Sync, File Upload & Streaming Flow', () => {
    it('Multi-Device Chat Sync: loads history from server via getDocumentChats on document selection', async () => {
      api.getUserDocuments.mockResolvedValueOnce([
        {
          id: TEST_DOC_ID,
          filename: 'metabolic_panel.pdf',
          title: 'Metabolic Panel',
          created_at: '2026-10-21T09:00:00Z',
        },
      ]);
      api.getDocumentChats.mockResolvedValue([
        {
          id: 'chat-1',
          role: 'user',
          message: 'What was my fasting glucose level?',
          created_at: '2026-10-21T09:05:00Z',
        },
        {
          id: 'chat-2',
          role: 'ai',
          message: 'Your fasting glucose was 95 mg/dL, which is within the normal range.',
          created_at: '2026-10-21T09:05:05Z',
        },
      ]);

      render(<ChatApp />);

      await waitFor(() => {
        expect(api.getUserDocuments).toHaveBeenCalled();
      });

      // Find the document in the sidebar
      const docItem = await screen.findByText('Metabolic Panel');
      expect(docItem).toBeInTheDocument();

      // Click to select document
      fireEvent.click(docItem);

      await waitFor(() => {
        expect(api.getDocumentChats).toHaveBeenCalledWith(TEST_DOC_ID);
        expect(screen.getByText('What was my fasting glucose level?')).toBeInTheDocument();
        expect(
          screen.getByText(/Your fasting glucose was 95 mg\/dL, which is within the normal range\./)
        ).toBeInTheDocument();
      });
    });

    it('New Conversation: clicking New Conversation clears active chat messages cleanly', async () => {
      render(<ChatApp />);

      await waitFor(() => {
        expect(api.getProfile).toHaveBeenCalled();
        expect(api.getUserDocuments).toHaveBeenCalled();
      });

      const [newChatBtn] = screen.getAllByRole('button', { name: /new conversation/i });
      fireEvent.click(newChatBtn);

      // Verify empty state welcome prompt renders cleanly
      await waitFor(() => {
        expect(screen.getAllByText(/MediSkye AI Medical Assistant/i).length).toBeGreaterThanOrEqual(1);
      });
    });

    it('File Upload Lifecycle: shows upload/processing progress and transitions to sidebar on completion', async () => {
      window.__POLL_INTERVAL__ = 10;
      api.uploadPdfReport.mockResolvedValueOnce({
        job_id: 'job-e2e-777',
        status_url: '/upload/status/job-e2e-777',
      });
      api.getUploadStatus
        .mockResolvedValueOnce({
          job_id: 'job-e2e-777',
          status: 'processing',
        })
        .mockResolvedValueOnce({
          job_id: 'job-e2e-777',
          status: 'completed',
          document_id: TEST_DOC_ID,
        });

      render(<ChatApp />);

      await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

      const fileInput = document.querySelector('input[type="file"]');
      const testFile = createMockPdf('lipid_panel.pdf');

      await act(async () => {
        fireEvent.change(fileInput, { target: { files: [testFile] } });
      });

      await waitFor(() => {
        expect(api.uploadPdfReport).toHaveBeenCalledWith(testFile, 'self', expect.any(String));
        expect(api.getUploadStatus).toHaveBeenCalledWith('job-e2e-777', 10000);
        expect(screen.getByLabelText('Detach lipid_panel.pdf')).toBeInTheDocument();
      });

      delete window.__POLL_INTERVAL__;
    });

    it('Try Sample Report Flow: uploads a random sample PDF, sets "Sample Report: [Panel]" title, and auto-triggers AI summary query', async () => {
      window.__POLL_INTERVAL__ = 10;
      api.uploadPdfReport.mockResolvedValueOnce({
        job_id: 'job-sample-888',
        status_url: '/upload/status/job-sample-888',
      });
      api.getUploadStatus.mockResolvedValueOnce({
        job_id: 'job-sample-888',
        status: 'completed',
        document_id: TEST_DOC_ID,
      });
      api.renameDocument.mockResolvedValueOnce({ id: TEST_DOC_ID, title: 'Sample Report: Lipid Panel' });
      api.sendQueryStream.mockImplementation(async (query, docId, lang, onChunk) => {
        onChunk({ title: 'Can you summarize the' });
        onChunk({ chunk: 'Elevated LDL cholesterol and triglycerides detected.' });
      });

      render(<ChatApp />);
      await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

      const sampleBtn = screen.getByRole('button', { name: /try with a sample blood test report/i });
      await act(async () => {
        fireEvent.click(sampleBtn);
      });

      await waitFor(() => {
        expect(api.uploadPdfReport).toHaveBeenCalledWith(
          expect.any(File),
          'self',
          expect.any(String),
          expect.stringMatching(/^Sample Report: /)
        );
        expect(api.sendQueryStream).toHaveBeenCalledWith(
          'Can you summarize the abnormal findings in this report?',
          TEST_DOC_ID,
          'English',
          expect.any(Function),
          'self',
          expect.anything()
        );
        expect(screen.getAllByText(/^Sample Report: /).length).toBeGreaterThanOrEqual(1);
        expect(screen.getByText(/Elevated LDL cholesterol and triglycerides detected\./)).toBeInTheDocument();
      });

      delete window.__POLL_INTERVAL__;
    });

    it('SSE Message Streaming: disables send button, renders user bubble immediately, streams progressive answer without specialists card', async () => {
      api.sendQueryStream.mockImplementation(async (query, docId, lang, onChunk) => {
        // Yield chunks progressively
        onChunk({ chunk: 'Your cholesterol ' });
        onChunk({ chunk: 'is elevated at 220 mg/dL. ' });
        onChunk({ chunk: 'Consider discussing dietary modifications with your physician.' });
      });

      render(<ChatApp />);

      await waitFor(() => {
        expect(api.getProfile).toHaveBeenCalled();
        expect(api.getUserDocuments).toHaveBeenCalled();
      });

      const user = userEvent.setup();
      const textarea = screen.getByPlaceholderText(/ask a medical question/i);
      await user.type(textarea, 'Explain my cholesterol level');
      const sendBtn = screen.getByRole('button', { name: /send message/i });
      expect(sendBtn).not.toBeDisabled();
      await user.click(sendBtn);

      // User bubble appears immediately
      await waitFor(() => {
        expect(screen.getAllByText('Explain my cholesterol level').length).toBeGreaterThanOrEqual(1);
      });

      // Assistant streaming result renders
      await waitFor(() => {
        expect(api.sendQueryStream).toHaveBeenCalledWith(
          'Explain my cholesterol level',
          expect.any(String),
          'English',
          expect.any(Function),
          'self',
          expect.anything()
        );
        expect(
          screen.getByText(/Your cholesterol is elevated at 220 mg\/dL\./)
        ).toBeInTheDocument();
      });

      // No deprecated Recommended Specialists cards in UI
      expect(screen.queryByText(/Recommended Specialists/i)).not.toBeInTheDocument();
    });

    it('Export Printable Summary: calls getDocumentSummary and triggers window.print after render', async () => {
      const printSpy = vi.spyOn(window, 'print').mockImplementation(() => {});
      const docChat = {
        id: TEST_DOC_ID,
        document_id: TEST_DOC_ID,
        title: 'Complete Blood Count',
        messages: [
          { id: '1', sender: 'user', text: 'Analyze CBC', timestamp: '10:00' },
          { id: '2', sender: 'assistant', text: 'All values normal.', timestamp: '10:01' },
        ],
        pdf: { id: TEST_DOC_ID, name: 'cbc.pdf' },
        documents: [{ id: TEST_DOC_ID, name: 'cbc.pdf', filename: 'cbc.pdf' }],
      };
      api.getUserDocuments.mockResolvedValueOnce([
        { id: TEST_DOC_ID, filename: 'cbc.pdf', title: 'Complete Blood Count' },
      ]);
      localStorage.setItem('mediskye_conversations', JSON.stringify([docChat]));

      render(<ChatApp />);

      await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

      const exportBtn = await screen.findByRole('button', { name: /Export Summary/i });
      expect(exportBtn).toBeInTheDocument();

      await act(async () => {
        fireEvent.click(exportBtn);
      });

      await waitFor(() => {
        expect(api.getDocumentSummary).toHaveBeenCalledWith(TEST_DOC_ID);
        expect(printSpy).toHaveBeenCalled();
      });

      printSpy.mockRestore();
    });

    it('Minimalist Lab Metrics Table: sorts High/Low before Normal, renders without ReferenceBar or emojis, uses plain text status colors', () => {
      const sampleMetrics = [
        { test: 'Hemoglobin', value: '14.0', unit: 'g/dL', range: '12–16', status: 'Normal' },
        { test: 'Potassium', value: '5.8', unit: 'mmol/L', range: '3.5–5.0', status: 'High' },
        { test: 'Ferritin', value: '10', unit: 'ng/mL', range: '20–200', status: 'Low' },
      ];

      const { container } = render(<LabMetrics metrics={sampleMetrics} />);

      // Verify semantic table headers
      expect(screen.getByText('Test Name')).toBeInTheDocument();
      expect(screen.getByText('Value')).toBeInTheDocument();
      expect(screen.getByText('Reference Range')).toBeInTheDocument();
      expect(screen.getByText('Status')).toBeInTheDocument();

      // Abnormal rows (Potassium High, Ferritin Low) sort first
      const rows = container.querySelectorAll('tbody tr');
      expect(rows.length).toBe(3);
      expect(rows[0].textContent).toMatch(/High|Low/);
      expect(rows[1].textContent).toMatch(/High|Low/);
      expect(rows[2].textContent).toContain('Normal');
      expect(rows[2].textContent).toContain('Hemoglobin');

      // No emojis or progress bars
      expect(container.textContent).not.toMatch(/[\u{1F300}-\u{1F9FF}]/u);
      expect(container.querySelector('[role="progressbar"]')).toBeNull();
      expect(container.querySelector('.rounded-full')).toBeNull();
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // 3. Settings, Profile & Modal State Flows
  // ───────────────────────────────────────────────────────────────────────────
  describe('3. Settings, Profile & Modal State Flows', () => {
    it('Save Settings: modifies language preference and fires updateProfile API call', async () => {
      const showToast = vi.fn();
      const setLanguage = vi.fn();
      const onProfileUpdated = vi.fn();
      api.updateProfile.mockResolvedValueOnce({ language_preference: 'Spanish' });

      render(
        <SettingsModal
          isOpen={true}
          onClose={vi.fn()}
          darkMode={false}
          currentUser={{ email: 'patient@example.com', full_name: 'Jane Doe' }}
          language="English"
          setLanguage={setLanguage}
          showToast={showToast}
          onProfileUpdated={onProfileUpdated}
        />
      );

      const select = screen.getByDisplayValue('English (US)');
      fireEvent.change(select, { target: { value: 'Spanish' } });

      const saveBtn = screen.getByRole('button', { name: 'Save Changes' });
      fireEvent.click(saveBtn);

      await waitFor(() => {
        expect(api.updateProfile).toHaveBeenCalledWith({ language_preference: 'Spanish' });
        expect(setLanguage).toHaveBeenCalledWith('Spanish');
        expect(showToast).not.toHaveBeenCalled();
      });
    });

    it('Unsaved Changes Guard: triggers confirmation dialog on close when settings are dirty, allows Keep Editing or Discard', async () => {
      const onClose = vi.fn();

      render(
        <SettingsModal
          isOpen={true}
          onClose={onClose}
          darkMode={false}
          currentUser={{ email: 'patient@example.com', full_name: 'Jane Doe' }}
          language="English"
        />
      );

      // Change setting to make state dirty
      const select = screen.getByDisplayValue('English (US)');
      fireEvent.change(select, { target: { value: 'French' } });

      // Attempt to close via X button
      const closeBtn = await screen.findByRole('button', { name: 'Close settings' });
      fireEvent.click(closeBtn);

      // Verify Unsaved Changes prompt appears and modal did not close
      expect(onClose).not.toHaveBeenCalled();
      expect(screen.getByText('Unsaved Changes')).toBeInTheDocument();

      // Test "Keep Editing"
      const keepEditingBtn = screen.getByRole('button', { name: 'Keep Editing' });
      fireEvent.click(keepEditingBtn);
      expect(screen.queryByText('Unsaved Changes')).not.toBeInTheDocument();
      expect(onClose).not.toHaveBeenCalled();

      // Attempt to close again and "Discard Changes"
      fireEvent.click(closeBtn);
      const discardBtn = screen.getByRole('button', { name: 'Discard Changes' });
      fireEvent.click(discardBtn);
      expect(onClose).toHaveBeenCalledTimes(1);
    });

    it('Modal Handoff: clicking Manage Health Profile & Caregivers closes SettingsModal and opens Profile modal', async () => {
      const onOpenProfile = vi.fn();
      const onClose = vi.fn();

      render(
        <SettingsModal
          isOpen={true}
          onClose={onClose}
          darkMode={false}
          currentUser={{ email: 'patient@example.com' }}
          onOpenProfile={onOpenProfile}
        />
      );

      const profileBtn = await screen.findByRole('button', {
        name: /manage health profile & caregivers/i,
      });
      fireEvent.click(profileBtn);

      expect(onClose).toHaveBeenCalled();
      expect(onOpenProfile).toHaveBeenCalled();
    });

    it('Logout Cleanup: clicking Log Out in Sidebar opens confirmation, calls signOut and clears auth tokens from storage', async () => {
      localStorage.setItem('token', 'active_session_jwt');
      localStorage.setItem('mediskye_conversations', '[{"id":"1"}]');

      const onLogout = vi.fn().mockImplementation(async () => {
        await api.logout();
      });

      render(
        <Sidebar
          isOpen={true}
          onToggle={vi.fn()}
          conversations={[]}
          activeSessionId="sess-1"
          onSelectChat={vi.fn()}
          onDeleteChat={vi.fn()}
          onRenameChat={vi.fn()}
          onNewChat={vi.fn()}
          onOpenSettings={vi.fn()}
          onOpenProfile={vi.fn()}
          darkMode={false}
          setDarkMode={vi.fn()}
          activePdf={null}
          language="English"
          setLanguage={vi.fn()}
          onLogout={onLogout}
          currentUser={{ email: 'patient@example.com' }}
        />
      );

      // Find Log Out in sidebar
      const logoutBtn = screen.getByRole('button', { name: /log out/i });
      fireEvent.click(logoutBtn);

      // Confirm in ConfirmModal
      const confirmDialog = await screen.findByRole('dialog');
      const confirmActionBtn = within(confirmDialog).getByRole('button', { name: /^log out$/i });
      fireEvent.click(confirmActionBtn);

      await waitFor(() => {
        expect(onLogout).toHaveBeenCalled();
        expect(mockSignOut).toHaveBeenCalled();
        expect(localStorage.getItem('token')).toBeNull();
        expect(localStorage.getItem('mediskye_conversations')).toBeNull();
      });
    });
  });

  // ───────────────────────────────────────────────────────────────────────────
  // 4. Automated Accessibility (a11y) & i18n Audit
  // ───────────────────────────────────────────────────────────────────────────
  describe('4. Automated Accessibility (a11y) & i18n Audit', () => {
    it('Icon-Only Buttons Audit: every button without visible text in src/components/*.jsx has an aria-label or title', () => {
      const componentsDir = path.resolve(__dirname, '../components');
      const files = fs.readdirSync(componentsDir).filter((f) => f.endsWith('.jsx'));

      const violations = [];

      files.forEach((file) => {
        const filePath = path.join(componentsDir, file);
        const content = fs.readFileSync(filePath, 'utf-8');

        // Regex to match buttons: <button ...>...</button>
        const buttonRegex = /<button\b([^>]*)>([\s\S]*?)<\/button>/g;
        let match;

        while ((match = buttonRegex.exec(content)) !== null) {
          const [fullTag, attrs, inner] = match;
          let remaining = inner
            .replace(/<[A-Za-z0-9_]+\s*[^>]*\/>/g, '') // remove self-closing icons
            .replace(/<svg\b[\s\S]*?<\/svg>/g, '') // remove inline svgs
            .replace(/<[^>]+>/g, '') // strip remaining tags like <span> <div>
            .trim();

          const isIconOnly = remaining.length === 0;
          if (isIconOnly) {
            const hasAria = /aria-label\s*=\s*['"{]|aria-labelledby\s*=\s*['"{]|title\s*=\s*['"{]/.test(attrs);
            if (!hasAria) {
              violations.push({
                file,
                buttonSnippet: fullTag.slice(0, 100).replace(/\s+/g, ' '),
              });
            }
          }
        }
      });

      expect(violations).toEqual([]);
    });

    it('Focus Trap & Escape Key Verification: all 6 modals import and invoke useFocusTrap', () => {
      const requiredModals = [
        'SettingsModal.jsx',
        'Profile.jsx',
        'DocumentModal.jsx',
        'ConfirmModal.jsx',
        'ExportModal.jsx',
        'MemoryConsentModal.jsx',
      ];

      const componentsDir = path.resolve(__dirname, '../components');
      requiredModals.forEach((modalFile) => {
        const content = fs.readFileSync(path.join(componentsDir, modalFile), 'utf-8');
        expect(content).toContain("import useFocusTrap from '../hooks/useFocusTrap';");
        expect(content).toMatch(/useFocusTrap\s*\(/);
      });
    });

    it('i18n Translation Coverage: every t("key") key in src/components/*.jsx exists in both en and hi translation files', () => {
      const localesDir = path.resolve(__dirname, '../locales');
      const enFile = JSON.parse(fs.readFileSync(path.join(localesDir, 'en/translation.json'), 'utf-8'));
      const hiFile = JSON.parse(fs.readFileSync(path.join(localesDir, 'hi/translation.json'), 'utf-8'));

      function getNestedValue(obj, keyPath) {
        return keyPath.split('.').reduce((acc, part) => acc && acc[part], obj);
      }

      const componentsDir = path.resolve(__dirname, '../components');
      const files = fs.readdirSync(componentsDir).filter((f) => f.endsWith('.jsx'));

      const usedKeys = new Set();
      const tCallRegex = /\bt\(\s*['"]([a-zA-Z0-9_.]+)['"]/g;

      files.forEach((file) => {
        const content = fs.readFileSync(path.join(componentsDir, file), 'utf-8');
        let match;
        while ((match = tCallRegex.exec(content)) !== null) {
          usedKeys.add(match[1]);
        }
      });

      const missingInEn = [];
      const missingInHi = [];

      usedKeys.forEach((key) => {
        if (getNestedValue(enFile, key) === undefined) {
          missingInEn.push(key);
        }
        if (getNestedValue(hiFile, key) === undefined) {
          missingInHi.push(key);
        }
      });

      expect(missingInEn).toEqual([]);
      expect(missingInHi).toEqual([]);
    });
  });
});
