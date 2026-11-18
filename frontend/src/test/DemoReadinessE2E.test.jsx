import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import * as api from '../services/api';
import ChatApp from '../components/ChatApp';

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
});
