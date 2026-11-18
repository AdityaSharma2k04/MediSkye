import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import * as api from '../services/api';
import ChatApp, { isMatchingConversation } from '../components/ChatApp';

// Mock routing and speech services
vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
  Navigate: ({ to }) => <div data-testid="navigate-mock">{to}</div>,
  BrowserRouter: ({ children }) => <div>{children}</div>,
  MemoryRouter: ({ children }) => <div>{children}</div>,
  Routes: ({ children }) => <div>{children}</div>,
  Route: ({ element }) => <div>{element}</div>,
}));

vi.mock('../services/speech', () => ({
  speakText: vi.fn(),
  stopSpeaking: vi.fn(),
}));

describe('MediSkye College Demo Readiness E2E Integration Suite', () => {
  const mockUser = {
    id: 'usr-aditya-1001',
    email: 'aditya.sharma@example.com',
    full_name: 'Aditya Sharma',
    memory_consent_granted: true,
  };

  const mockRohan = {
    id: 'dep-rohan-2002',
    full_name: 'Rohan Deshmukh',
    relationship: 'Child',
    birth_date: '2015-06-12',
    gender: 'male',
    document_count: 2,
    report_count: 2,
  };

  const mockDocBaseline = {
    id: 'doc-baseline-101',
    filename: 'Baseline_Blood_Test_10Jan2026.pdf',
    title: 'Baseline 10 Jan 2026',
    collected_at: '2026-01-10',
    dependent_id: 'dep-rohan-2002',
    patient_id: 'dep-rohan-2002',
    created_at: '2026-01-10T09:00:00Z',
    size: 15420,
  };

  const mockDocFollowUp = {
    id: 'doc-followup-102',
    filename: 'FollowUp_Metabolic_Panel_21Sep2026.pdf',
    title: 'Follow-Up 21 Sep 2026',
    collected_at: '2026-09-21',
    dependent_id: 'dep-rohan-2002',
    patient_id: 'dep-rohan-2002',
    created_at: '2026-09-21T10:30:00Z',
    size: 18230,
  };

  const rohanDocs = [mockDocBaseline, mockDocFollowUp];

  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
    api.RAM_CACHE.clear();
    api.resetBootSyncStatus();

    // Prevent window.scrollTo from failing in jsdom
    window.scrollTo = vi.fn();
    window.print = vi.fn();

    // Simulate boot sync already completed so hydration overlay never blocks
    const stableUid = api.getStableCacheUid();
    api.markBootSyncCompleted(stableUid);

    // Default API mocks
    vi.spyOn(api, 'getProfile').mockResolvedValue(mockUser);
    vi.spyOn(api, 'getDependents').mockResolvedValue([mockRohan]);
    vi.spyOn(api, 'getUserDocuments').mockImplementation(async (depId) => {
      if (depId === 'dep-rohan-2002') return rohanDocs;
      return [];
    });
    vi.spyOn(api, 'getChatSessions').mockResolvedValue([]);
    vi.spyOn(api, 'getDocumentChats').mockResolvedValue([]);
    vi.spyOn(api, 'getGeneralChats').mockResolvedValue([]);
    vi.spyOn(api, 'fetchLabMetrics').mockResolvedValue([
      { name: 'Hemoglobin', value: 13.5, unit: 'g/dL', status: 'normal' },
      { name: 'Ferritin', value: 45, unit: 'ng/mL', status: 'normal' },
      { name: 'Total Cholesterol', value: 165, unit: 'mg/dL', status: 'normal' },
    ]);
    vi.spyOn(api, 'getMetricTrends').mockResolvedValue({ series: [] });
    vi.spyOn(api, 'getMemoryFacts').mockResolvedValue([]);
    vi.spyOn(api, 'getMemoryStatus').mockResolvedValue({ memory_consent_granted: true });
    vi.spyOn(api, 'exportDocumentData').mockResolvedValue({
      document: mockDocBaseline,
      messages: [],
      lab_metrics: [],
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('executes full college demo presentation flow: profile switch -> doc chat multi-turn streaming with markdown table -> cache rehydration -> export modal', async () => {
    let streamCallCount = 0;
    const streamSpy = vi.spyOn(api, 'sendQueryStream').mockImplementation(async (query, docId, lang, onChunk) => {
      streamCallCount += 1;
      if (streamCallCount === 1) {
        onChunk({
          session_id: 'session-rohan-demo-1',
          title: 'Baseline Longitudinal Analysis',
        });
        const tableMarkdown = `Here is the longitudinal comparison for Rohan:

| Biomarker | Baseline (10 Jan) | Follow-Up (21 Sep) | Change | Status |
| :--- | :--- | :--- | :--- | :--- |
| Hemoglobin | 11.2 g/dL | 13.5 g/dL | +2.3 | Normalized |
| Ferritin | 14 ng/mL | 45 ng/mL | +31 | Optimal |
| Total Cholesterol | 185 mg/dL | 165 mg/dL | -20 | Desirable |

All critical biomarkers have normalized since starting therapy.`;
        onChunk({ chunk: tableMarkdown });
      } else {
        onChunk({
          session_id: 'session-rohan-demo-1',
        });
        onChunk({ chunk: 'The ferritin increase of +31 ng/mL indicates successful iron repletion.' });
      }
    });

    const { container } = render(<ChatApp />);

    // Initial render settles
    await waitFor(() => {
      expect(api.getProfile).toHaveBeenCalled();
      expect(api.getDependents).toHaveBeenCalled();
    });

    // 1. Confirm NO hydration / "Setting up your workbench" blocking screen is rendered
    expect(screen.queryByText(/Setting up your workbench/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Please wait while we load your clinical database/i)).not.toBeInTheDocument();

    // 2. Profile Switcher: Switch from "Self" (Aditya Sharma) to "Rohan Deshmukh"
    const switcherTrigger = screen.getByTestId('patient-switcher-trigger');
    expect(switcherTrigger).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(switcherTrigger);
    });

    // Look for Rohan Deshmukh option and select it
    const rohanOption = await screen.findByText('Rohan Deshmukh');
    expect(rohanOption).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(rohanOption.closest('button'));
    });

    // Verify 0ms profile switch: NO hydration overlay appears!
    expect(screen.queryByText(/Setting up your workbench/i)).not.toBeInTheDocument();
    expect(screen.getByTestId('patient-switcher-trigger')).toHaveTextContent('Rohan Deshmukh');

    // 3. Document Selection: Rohan's reports appear in the sidebar/document list
    const baselineDocItem = await screen.findByText('Baseline 10 Jan 2026');
    expect(baselineDocItem).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(baselineDocItem.closest('button'));
    });

    // 4. Send Question 1 in Rohan's Document Chat
    const chatInput = screen.getByPlaceholderText(/Ask about this report|Ask MediSkye/i);
    expect(chatInput).toBeInTheDocument();

    fireEvent.change(chatInput, {
      target: { value: "How have Rohan's lab results changed between baseline and follow-up?" },
    });

    const chatForm = chatInput.closest('form');
    await act(async () => {
      fireEvent.submit(chatForm);
    });

    // Verify stream called with document ID
    await waitFor(() => {
      expect(streamSpy).toHaveBeenCalledTimes(1);
    });

    // A. Assert User Question Bubble
    const q1Bubble = await screen.findByText("How have Rohan's lab results changed between baseline and follow-up?");
    expect(q1Bubble).toBeInTheDocument();

    // The user's bubble must NOT have a "MediSkye AI" header
    const q1BubbleContainer = q1Bubble.closest('.group') || q1Bubble.parentElement;
    expect(q1BubbleContainer.textContent).not.toContain('MediSkye AI');

    // Timestamps must NOT be raw ISO strings
    expect(container.textContent).not.toContain('2026-11-18T');
    expect(container.textContent).not.toContain('+00:00');

    // B. Assert Assistant Response with Markdown Table
    expect(await screen.findByText(/Here is the longitudinal comparison for Rohan/i)).toBeInTheDocument();
    expect(screen.getByText('Hemoglobin')).toBeInTheDocument();
    expect(screen.getByText('11.2 g/dL')).toBeInTheDocument();
    expect(screen.getByText('13.5 g/dL')).toBeInTheDocument();
    expect(screen.getByText('Normalized')).toBeInTheDocument();
    expect(screen.getByText('Ferritin')).toBeInTheDocument();
    expect(screen.getByText('Total Cholesterol')).toBeInTheDocument();

    // C. Verify Markdown Table Overflow Container
    const tableEl = container.querySelector('table');
    expect(tableEl).toBeInTheDocument();
    const tableContainer = tableEl.closest('.ms-table-card');
    expect(tableContainer).toBeInTheDocument();
    expect(tableContainer.className).toContain('overflow-x-auto');

    // 5. Send Question 2 (Follow-up) in the exact same chat
    // Allow ChatInput submission cooldown (300ms) and generation settling
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });

    const chatInputQ2 = screen.getByPlaceholderText(/Ask about this report|Ask MediSkye/i);
    fireEvent.change(chatInputQ2, {
      target: { value: 'Is the ferritin increase safe and expected?' },
    });

    const chatFormQ2 = chatInputQ2.closest('form');
    await act(async () => {
      fireEvent.submit(chatFormQ2);
    });

    await waitFor(() => {
      expect(streamSpy).toHaveBeenCalledTimes(2);
    });

    // Verify Question 2 and Answer 2 appear
    expect(await screen.findByText('Is the ferritin increase safe and expected?')).toBeInTheDocument();
    expect(await screen.findByText(/The ferritin increase of \+31 ng\/mL indicates successful iron repletion\./i)).toBeInTheDocument();

    // Verify Question 1 and Answer 1 are STILL in the DOM (order preserved)
    expect(screen.getByText("How have Rohan's lab results changed between baseline and follow-up?")).toBeInTheDocument();
    expect(screen.getByText(/Here is the longitudinal comparison for Rohan/i)).toBeInTheDocument();

    // 6. Cache Rehydration Verification: verify RAM_CACHE has both messages saved
    const cachedDocMsgs = api.getCachedChatMessages('doc_doc-baseline-101');
    expect(cachedDocMsgs.length).toBeGreaterThanOrEqual(4);
    expect(cachedDocMsgs[0].role).toBe('user');
    expect(cachedDocMsgs[0].sender).toBe('user');
    expect(cachedDocMsgs[1].role).toBe('assistant');
    expect(cachedDocMsgs[1].sender).toBe('ai');
    expect(cachedDocMsgs[2].role).toBe('user');
    expect(cachedDocMsgs[3].role).toBe('assistant');

    // 7. Test Export Modal: Open and close without triggering hydration screen
    const exportBtn = screen.getByLabelText('Export chat data');
    expect(exportBtn).toBeInTheDocument();

    await act(async () => {
      fireEvent.click(exportBtn);
    });

    // Assert Export Dialog is rendered
    expect(await screen.findByText('Export Chat Data')).toBeInTheDocument();

    // Close Export Dialog
    const closeExportBtn = screen.getByLabelText('Close export dialog');
    await act(async () => {
      fireEvent.click(closeExportBtn);
    });

    // Assert Export Dialog closed
    await waitFor(() => {
      expect(screen.queryByText('Export Chat Data')).not.toBeInTheDocument();
    });

    // Assert hydration screen NEVER reappears after dialog closes
    expect(screen.queryByText(/Setting up your workbench/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/Please wait while we load your clinical database/i)).not.toBeInTheDocument();

    // Chat messages are still intact
    expect(screen.getByText("How have Rohan's lab results changed between baseline and follow-up?")).toBeInTheDocument();
    expect(screen.getByText('Is the ferritin increase safe and expected?')).toBeInTheDocument();
  });

  it('isMatchingConversation correctly matches across doc_ prefix, document_id, and session_id', () => {
    const docConv = {
      id: 'doc_report-123',
      document_id: 'report-123',
      session_id: 'srv-sess-456',
      pdf: { id: 'report-123' },
    };

    expect(isMatchingConversation(docConv, 'report-123')).toBe(true);
    expect(isMatchingConversation(docConv, 'doc_report-123')).toBe(true);
    expect(isMatchingConversation(docConv, 'srv-sess-456')).toBe(true);
    expect(isMatchingConversation(docConv, 'other-id', 'report-123')).toBe(true);
    expect(isMatchingConversation(docConv, 'other-id', 'doc_report-123')).toBe(true);
    expect(isMatchingConversation(docConv, 'unrelated-id')).toBe(false);

    const generalConv = {
      id: 'gen-uuid-999',
      session_id: 'gen-uuid-999',
    };
    expect(isMatchingConversation(generalConv, 'gen-uuid-999')).toBe(true);
    expect(isMatchingConversation(generalConv, 'other-gen')).toBe(false);
  });

  it('Test A (Normal General Chat): renders live streamed answer and 2nd follow-up in active window without reload or re-clicking sidebar', async () => {
    let callCount = 0;
    const streamSpy = vi.spyOn(api, 'sendQueryStream').mockImplementation(async (query, docId, lang, onChunk) => {
      callCount += 1;
      if (callCount === 1) {
        onChunk({
          session_id: 'gen-uuid-999',
          title: 'Vitamin D Inquiry',
        });
        onChunk({ chunk: 'Early signs of Vitamin D deficiency include ' });
        onChunk({ chunk: 'fatigue, bone pain, and muscle weakness.' });
      } else {
        onChunk({
          session_id: 'gen-uuid-999',
        });
        onChunk({ chunk: 'You can improve levels via safe sunlight exposure and D3 supplements.' });
      }
    });

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    // Verify on general chat (no report attached)
    const chatInput = screen.getByPlaceholderText(/Ask a medical question|Ask about this report|Ask MediSkye/i);
    expect(chatInput).toBeInTheDocument();

    // 1. Send first general question
    fireEvent.change(chatInput, {
      target: { value: 'What are early signs of Vitamin D deficiency?' },
    });
    const form = chatInput.closest('form');
    await act(async () => {
      fireEvent.submit(form);
    });

    // Assert Question 1 appears in active thread
    expect(await screen.findByText('What are early signs of Vitamin D deficiency?')).toBeInTheDocument();

    // Assert that a real UUID v4 was minted before sendQueryStream was called (not a new_ draft ID)
    expect(streamSpy.mock.calls[0][1]).not.toMatch(/^new_/);
    expect(streamSpy.mock.calls[0][1]).toMatch(/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);

    // Assert Answer 1 renders LIVE in active thread without reloading or re-clicking sidebar
    expect(await screen.findByText(/fatigue, bone pain, and muscle weakness\./i)).toBeInTheDocument();

    // Wait for submission cooldown
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });

    // 2. Send second follow-up question in the same general chat
    const chatInputQ2 = screen.getByPlaceholderText(/Ask a medical question|Ask about this report|Ask MediSkye/i);
    fireEvent.change(chatInputQ2, {
      target: { value: 'How can I improve my Vitamin D levels?' },
    });
    const formQ2 = chatInputQ2.closest('form');
    await act(async () => {
      fireEvent.submit(formQ2);
    });

    // Assert Question 2 appears in active thread
    expect(await screen.findByText('How can I improve my Vitamin D levels?')).toBeInTheDocument();

    // Assert Answer 2 renders LIVE in active thread without reloading or re-clicking sidebar
    expect(await screen.findByText(/You can improve levels via safe sunlight exposure and D3 supplements\./i)).toBeInTheDocument();

    // Assert both Q1+A1 and Q2+A2 remain in DOM in order
    expect(screen.getByText('What are early signs of Vitamin D deficiency?')).toBeInTheDocument();
    expect(screen.getByText(/fatigue, bone pain, and muscle weakness\./i)).toBeInTheDocument();
  });

  it('Test B (Post-Report Follow-Up With doc_ ID Mismatch): renders streamed follow-up on existing report where c.id="doc_report-123", document_id="report-123", session_id="srv-sess-456"', async () => {
    const reportDocId = 'report-123';
    const reportConvId = 'doc_report-123';
    const reportServerSessId = 'srv-sess-456';

    const mockReport = {
      id: reportDocId,
      filename: 'Metabolic_Panel.pdf',
      title: 'Comprehensive Metabolic Panel',
      collected_at: '2026-03-15',
      dependent_id: null,
      patient_id: 'self',
      created_at: '2026-03-15T08:00:00Z',
    };

    // Pre-seed conversation with doc_ prefix and server session_id
    const existingMessages = [
      api.normalizeChatMessage({ id: 'u1', sender: 'user', content: 'What is my fasting glucose?' }),
      api.normalizeChatMessage({ id: 'a1', sender: 'ai', content: 'Your fasting glucose is 95 mg/dL, which is within the normal reference range.' }),
    ];

    api.getUserDocuments.mockResolvedValue([mockReport]);
    api.getDocumentChats.mockResolvedValue(existingMessages);
    api.setCachedChatMessages(`doc_${reportDocId}`, existingMessages);

    let streamCalled = false;
    vi.spyOn(api, 'sendQueryStream').mockImplementation(async (query, docId, lang, onChunk) => {
      streamCalled = true;
      onChunk({
        session_id: reportServerSessId,
      });
      onChunk({ chunk: 'Yes, 95 mg/dL is an optimal normal fasting level.' });
    });

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    // Switch to the existing report in the sidebar
    const reportItem = await screen.findByText('Comprehensive Metabolic Panel');
    await act(async () => {
      fireEvent.click(reportItem.closest('button'));
    });

    // Verify existing Q1 and A1 are loaded
    expect(await screen.findByText('What is my fasting glucose?')).toBeInTheDocument();
    expect(await screen.findByText(/Your fasting glucose is 95 mg\/dL/i)).toBeInTheDocument();

    // Allow cooldown
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 350));
    });

    // Send follow-up question
    const chatInput = screen.getByPlaceholderText(/Ask about this report|Ask MediSkye/i);
    fireEvent.change(chatInput, {
      target: { value: 'Is 95 mg/dL optimal for fasting glucose?' },
    });
    const form = chatInput.closest('form');
    await act(async () => {
      fireEvent.submit(form);
    });

    // Assert stream was invoked
    await waitFor(() => expect(streamCalled).toBe(true));

    // Assert follow-up question and LIVE streamed answer appear in the window immediately
    expect(await screen.findByText('Is 95 mg/dL optimal for fasting glucose?')).toBeInTheDocument();
    expect(await screen.findByText('Yes, 95 mg/dL is an optimal normal fasting level.')).toBeInTheDocument();

    // Assert initial Q1+A1 are STILL present
    expect(screen.getByText('What is my fasting glucose?')).toBeInTheDocument();
    expect(screen.getByText(/Your fasting glucose is 95 mg\/dL/i)).toBeInTheDocument();
  });

  it('persists active dependent profile across page reload (mount with cached dependent)', async () => {
    // 1. Simulate prior session where Rohan was active and cached
    api.setCachedProfile(mockUser);
    api.setCachedDependents([mockRohan]);
    localStorage.setItem('mediskye_patient_id', mockRohan.id);

    // 2. Mount ChatApp (simulating a page reload)
    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    // 3. Verify that mediskye_patient_id was NOT overwritten to 'self'
    expect(localStorage.getItem('mediskye_patient_id')).toBe(mockRohan.id);

    // 4. Verify Rohan's name is rendered as the active profile
    expect(await screen.findByText('Rohan Deshmukh')).toBeInTheDocument();
  });

  it('persists active dependent on cold reload when getCachedDependents is initially empty and verifies sendQueryStream call signatures', async () => {
    // 1. Simulate cold reload: mediskye_patient_id exists in localStorage, but RAM cache / cachedDependents is empty
    localStorage.setItem('mediskye_patient_id', mockRohan.id);
    expect(api.getCachedDependents()).toEqual([]);

    // Spy on sendQueryStream
    let capturedArgs = null;
    vi.spyOn(api, 'sendQueryStream').mockImplementation(async (query, docId, lang, onChunk, patientId, signal, sessionId) => {
      capturedArgs = { query, docId, lang, patientId, signal, sessionId };
      onChunk({ chunk: 'I am here to help you.' });
    });

    // 2. Mount ChatApp
    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());
    await waitFor(() => expect(api.getDependents).toHaveBeenCalled());

    // 3. Verify that mediskye_patient_id stays Rohan's ID (not wiped to 'self')
    expect(localStorage.getItem('mediskye_patient_id')).toBe(mockRohan.id);
    expect(await screen.findByText('Rohan Deshmukh')).toBeInTheDocument();

    // 4. Send a query in normal general chat for Rohan
    const chatInput = screen.getByPlaceholderText(/Ask a medical question|Ask about this report|Ask MediSkye/i);
    fireEvent.change(chatInput, {
      target: { value: 'How is Rohan doing today?' },
    });
    const form = chatInput.closest('form');
    await act(async () => {
      fireEvent.submit(form);
    });

    // 5. Verify sendQueryStream was called with patientId = mockRohan.id and valid session identifier
    await waitFor(() => expect(capturedArgs).not.toBeNull());
    expect(capturedArgs.query).toBe('How is Rohan doing today?');
    expect(typeof capturedArgs.docId).toBe('string');
    expect(capturedArgs.patientId).toBe(mockRohan.id); // Transmits active dependent!
    expect(capturedArgs.signal).toBeDefined();

    // Verify live answer rendered
    expect(await screen.findByText('I am here to help you.')).toBeInTheDocument();
  });

  it('refreshDocuments preserves cached messages and never wipes them with empty array when backend returns empty chats', async () => {
    const reportDocId = 'report-preserve-99';
    const mockReport = {
      id: reportDocId,
      filename: 'Liver_Function.pdf',
      title: 'Liver Function Test',
      collected_at: '2026-04-10',
      dependent_id: null,
      patient_id: 'self',
      created_at: '2026-04-10T08:00:00Z',
    };
    const cachedMessages = [
      api.normalizeChatMessage({ id: 'u-pres', sender: 'user', content: 'Explain ALT levels' }),
      api.normalizeChatMessage({ id: 'a-pres', sender: 'ai', content: 'Your ALT is 22 U/L which is normal.' }),
    ];
    api.getUserDocuments.mockResolvedValue([mockReport]);
    api.getDocumentChats.mockResolvedValue([]); // Backend returns empty array!
    api.setCachedChatMessages(`doc_${reportDocId}`, cachedMessages);

    render(<ChatApp />);
    await waitFor(() => expect(api.getProfile).toHaveBeenCalled());

    // Switch to the report
    const reportItem = await screen.findByText('Liver Function Test');
    await act(async () => {
      fireEvent.click(reportItem.closest('button'));
    });

    // Cached messages should be displayed immediately and preserved
    expect(await screen.findByText('Explain ALT levels')).toBeInTheDocument();
    expect(await screen.findByText('Your ALT is 22 U/L which is normal.')).toBeInTheDocument();
  });
});
