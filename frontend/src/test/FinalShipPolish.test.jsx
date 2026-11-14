import React from 'react';
import { render, screen, renderHook, waitFor, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import useLabMetrics, { extractBiomarkersFromMessage, invalidateMetrics } from '../hooks/useLabMetrics';
import Workbench from '../components/workbench/Workbench';
import ExternalAuthLanding from '../components/ExternalAuthLanding';
import * as api from '../services/api';

const mockFetchLabMetrics = vi.fn().mockResolvedValue([]);

vi.mock('../services/api', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    fetchLabMetrics: (...args) => mockFetchLabMetrics(...args),
  };
});

// Mock Firebase services
vi.mock('../services/firebase', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    auth: {},
    googleProvider: {},
    GoogleAuthProvider: {
      credentialFromResult: vi.fn().mockReturnValue({
        idToken: 'fake-id-token-123',
        accessToken: 'fake-access-token-456',
      }),
    },
    signInWithPopup: vi.fn().mockResolvedValue({
      user: {
        email: 'alex@example.com',
        getIdToken: vi.fn().mockResolvedValue('fake-id-token-123'),
      },
    }),
    onAuthStateChanged: vi.fn(),
    getFirebaseErrorMessage: vi.fn((err) => err?.message || 'Error'),
  };
});

describe('Task 3: Lab Metrics Report Loyalty & useLabMetrics Hook', () => {
  beforeEach(() => {
    invalidateMetrics();
    vi.restoreAllMocks();
  });

  it('extractBiomarkersFromMessage parses table rows accurately from Turn 1 markdown walkthrough', () => {
    const walkthrough = `
# Report Walkthrough
Here is the extracted blood panel:

| Test | Value | Unit | Reference Range | Status |
| --- | --- | --- | --- | --- |
| Hemoglobin | 14.2 | g/dL | 13.0 - 17.0 | Normal |
| Fasting Blood Glucose | 118 | mg/dL | 70 - 99 | High |
| Total Cholesterol | 240 | mg/dL | < 200 | High |
| Platelet Count | 2,38,000 | cells/mcL | 1,50,000 - 4,50,000 | Normal |
| TSH | 2.4 | uIU/mL | 0.4 - 4.0 | Normal |
`;
    const parsed = extractBiomarkersFromMessage(walkthrough);
    expect(parsed).toHaveLength(5);
    expect(parsed[0].name).toBe('Hemoglobin');
    expect(parsed[0].value).toBe('14.2');
    expect(parsed[1].name).toBe('Fasting Blood Glucose');
    expect(parsed[1].status).toBe('high');
    expect(parsed[3].name).toBe('Platelet Count');
    expect(parsed[3].value).toBe('2,38,000');
  });

  it('keeps canonical report metrics 100% immutable across follow-up questions (Turn 2, Turn 3)', async () => {
    const canonicalDocMetrics = [
      { name: 'Hemoglobin', value: '14.2', unit: 'g/dL', range: '13-17', status: 'normal' },
      { name: 'HbA1c', value: '6.8', unit: '%', range: '< 5.7', status: 'high' },
      { name: 'TSH', value: '3.1', unit: 'uIU/mL', range: '0.4-4.0', status: 'normal' },
      { name: 'Total Cholesterol', value: '235', unit: 'mg/dL', range: '< 200', status: 'high' },
      { name: 'Platelets', value: '2,50,000', unit: '/mcL', range: '150000-450000', status: 'normal' },
    ];

    mockFetchLabMetrics.mockResolvedValue(canonicalDocMetrics);

    // Initial render for doc_123
    const { result, rerender } = renderHook(
      ({ docId, messages }) => useLabMetrics(docId, { enabled: true, messages }),
      {
        initialProps: {
          docId: 'doc_123',
          messages: [
            { id: '1', sender: 'assistant', text: 'Turn 1 report walkthrough with data' },
          ],
        },
      }
    );

    await waitFor(() => {
      expect(result.current.metrics).toHaveLength(5);
      expect(result.current.loaded).toBe(true);
    });

    // Turn 2: Follow-up question arrives with conversational text without any biomarker table or flags
    rerender({
      docId: 'doc_123',
      messages: [
        { id: '1', sender: 'assistant', text: 'Turn 1 report walkthrough' },
        { id: '2', sender: 'user', text: 'What should I eat to lower my HbA1c?' },
        { id: '3', sender: 'assistant', text: 'Focus on high-fiber foods, lean proteins, and avoid refined sugars.' },
      ],
    });

    // Assert that metrics are completely preserved and NOT wiped or replaced
    expect(result.current.metrics).toHaveLength(5);
    expect(result.current.metrics[1].name).toBe('HbA1c');
    expect(result.current.metrics[1].status).toBe('high');

    // Turn 3: Another follow-up question
    rerender({
      docId: 'doc_123',
      messages: [
        { id: '1', sender: 'assistant', text: 'Turn 1 report walkthrough' },
        { id: '2', sender: 'user', text: 'What about exercise?' },
        { id: '3', sender: 'assistant', text: 'Aim for 150 minutes of moderate aerobic exercise per week.' },
      ],
    });

    expect(result.current.metrics).toHaveLength(5);
  });
});

describe('Task 5: Compact WifiOff Badge & Offline Behavior', () => {
  it('renders compact square WifiOff icon badge with screen reader text when offline', () => {
    render(
      <Workbench
        isDesktop={true}
        isOnline={false}
        viewMode="chat"
        onViewModeChange={vi.fn()}
        currentUser={{ id: 'u1', email: 'test@example.com' }}
        dependents={[]}
        selectedPatientId="self"
        onSelectPatient={vi.fn()}
        messages={[]}
        conversations={[]}
        onOpenPalette={vi.fn()}
        onToggleInspector={vi.fn()}
      />
    );

    const badge = screen.getByTestId('offline-status-badge');
    expect(badge).toBeInTheDocument();
    expect(badge.className).toContain('w-8 h-8');
    // Ensure screen-reader text 'Offline' is present for accessibility
    expect(badge.textContent).toContain('Offline');
  });

  it('hides offline status badge when online', () => {
    render(
      <Workbench
        isDesktop={true}
        isOnline={true}
        viewMode="chat"
        onViewModeChange={vi.fn()}
        currentUser={{ id: 'u1', email: 'test@example.com' }}
        dependents={[]}
        selectedPatientId="self"
        onSelectPatient={vi.fn()}
        messages={[]}
        conversations={[]}
        onOpenPalette={vi.fn()}
        onToggleInspector={vi.fn()}
      />
    );

    expect(screen.queryByTestId('offline-status-badge')).not.toBeInTheDocument();
  });
});

describe('Task 4: Parallel Sync & Workspace Hydration Overlay', () => {
  it('does not emit offline status on client AbortError', async () => {
    const emitSpy = vi.spyOn(api, 'emitConnectivityStatus');
    const controller = new AbortController();
    controller.abort();

    await expect(
      api.apiFetch('http://localhost:8000/api/v1/health', { signal: controller.signal })
    ).rejects.toThrow();

    // AbortError must NEVER trigger emitConnectivityStatus(false)
    expect(emitSpy).not.toHaveBeenCalledWith(false);
  });
});
