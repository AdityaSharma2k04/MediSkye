import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ChatApp from '../components/ChatApp';
import * as api from '../services/api';

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    getProfile: vi.fn().mockResolvedValue({
      id: 'user-primary-1',
      email: 'parent@example.com',
      full_name: 'Parent User',
      memory_consent_granted: true,
    }),
    getDependents: vi.fn().mockResolvedValue([
      { id: 'dep-child-1', full_name: 'Child Patient', relationship: 'Child' },
    ]),
    getUserDocuments: vi.fn().mockImplementation((patientId) => {
      const allDocs = [
        { id: 'doc-self-1', filename: 'self_blood_work.pdf', title: 'Self Blood Work', dependent_id: null },
        { id: 'doc-dep-1', filename: 'child_growth.pdf', title: 'Child Growth Chart', dependent_id: 'dep-child-1' },
      ];
      if (patientId === 'dep-child-1') {
        return Promise.resolve(allDocs.filter((d) => d.dependent_id === 'dep-child-1'));
      }
      if (patientId === 'self') {
        return Promise.resolve(allDocs.filter((d) => !d.dependent_id));
      }
      // If no patientId or un-isolated, return all
      return Promise.resolve(allDocs);
    }),
    getChatSessions: vi.fn().mockResolvedValue([]),
    getDocumentChats: vi.fn().mockResolvedValue([]),
    getGeneralChats: vi.fn().mockResolvedValue([]),
    fetchLabMetrics: vi.fn().mockResolvedValue([]),
    getMemoryStatus: vi.fn().mockResolvedValue({ memory_consent_granted: true }),
    getMemoryFacts: vi.fn().mockResolvedValue([]),
    getFacts: vi.fn().mockResolvedValue([]),
    getCachedProfile: vi.fn().mockReturnValue(null),
    getCachedDependents: vi.fn().mockReturnValue([
      { id: 'dep-child-1', full_name: 'Child Patient', relationship: 'Child' },
    ]),
    getCachedDocuments: vi.fn().mockImplementation((patientId) => {
      if (patientId === 'dep-child-1') {
        return [{ id: 'doc-dep-1', filename: 'child_growth.pdf', title: 'Child Growth Chart', dependent_id: 'dep-child-1' }];
      }
      if (patientId === 'self') {
        return [{ id: 'doc-self-1', filename: 'self_blood_work.pdf', title: 'Self Blood Work', dependent_id: null }];
      }
      return [];
    }),
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
    checkConnectivity: vi.fn().mockResolvedValue(true),
    emitConnectivityStatus: vi.fn(),
    API_BASE_URL: 'http://localhost:8000',
  };
});

describe('Profile Isolation & Switcher Tests (S1-S9)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    localStorage.setItem('mediskye_sidebar_open', 'true');
    window.innerWidth = 1024;
  });

  describe('S6 & S7: normalizePatientId helper', () => {
    it('normalizes falsy or "self" values to "self" and preserves UUIDs', () => {
      expect(typeof api.normalizePatientId).toBe('function');
      expect(api.normalizePatientId(undefined)).toBe('self');
      expect(api.normalizePatientId(null)).toBe('self');
      expect(api.normalizePatientId('')).toBe('self');
      expect(api.normalizePatientId('self')).toBe('self');
      expect(api.normalizePatientId('SELF')).toBe('self');
      expect(api.normalizePatientId('dep-child-1')).toBe('dep-child-1');
      expect(api.normalizePatientId('d4b6a9c1-1234-5678-9abc-def012345678')).toBe('d4b6a9c1-1234-5678-9abc-def012345678');
    });
  });

  describe('S1 & S2: Document list profile isolation across switching in ChatApp', () => {
    it('S1 & S2: Self shows only Self doc, switching to Child shows only Child doc', async () => {
      render(
        <MemoryRouter>
          <ChatApp />
        </MemoryRouter>
      );

      // Initially active is Self: Self Blood Work is shown, Child Growth Chart is NOT shown
      await waitFor(() => {
        expect(screen.getByText('Self Blood Work')).toBeInTheDocument();
      });
      expect(screen.queryByText('Child Growth Chart')).not.toBeInTheDocument();

      // Open PatientSwitcher
      const trigger = screen.getByTestId('patient-switcher-trigger');
      fireEvent.click(trigger);

      // Switch to Child Patient
      const childOption = await screen.findByText('Child Patient');
      fireEvent.click(childOption.closest('button'));

      // S1: After switching to Child, Child Growth Chart appears and Self Blood Work MUST NOT appear
      await waitFor(() => {
        expect(screen.getByText('Child Growth Chart')).toBeInTheDocument();
      });
      expect(screen.queryByText('Self Blood Work')).not.toBeInTheDocument();
    });
  });

  describe('S3: Switcher report counts', () => {
    it('displays independent report counts for Self and Dependent without bleeding', async () => {
      render(
        <MemoryRouter>
          <ChatApp />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Self Blood Work')).toBeInTheDocument();
      });

      const trigger = screen.getByTestId('patient-switcher-trigger');
      fireEvent.click(trigger);

      // Both Self and Child Patient have 1 report each; neither should show "No reports yet" or inflated 2
      await waitFor(() => {
        expect(screen.queryByText(/No reports yet/i)).not.toBeInTheDocument();
      });
    });
  });

  describe('S5: Standalone conversations isolation', () => {
    it('does not display Self standalone conversations under Child profile', async () => {
      api.getGeneralChats.mockImplementation((patientId) => {
        if (patientId === 'self' || !patientId) {
          return Promise.resolve([
            {
              id: 'chat-1',
              session_id: 'session-self-1',
              session_title: 'Self Symptoms Discussion',
              role: 'user',
              message: 'Fever check',
              dependent_id: null,
            },
          ]);
        }
        return Promise.resolve([]);
      });

      render(
        <MemoryRouter>
          <ChatApp />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Self Symptoms Discussion')).toBeInTheDocument();
      });

      // Switch to Child
      const trigger = screen.getByTestId('patient-switcher-trigger');
      fireEvent.click(trigger);
      const childOption = await screen.findByText('Child Patient');
      fireEvent.click(childOption.closest('button'));

      // Under Child profile, Self Symptoms Discussion MUST NOT be visible
      await waitFor(() => {
        expect(screen.queryByText('Self Symptoms Discussion')).not.toBeInTheDocument();
      });
    });
  });

  describe('S8: Document mapping respects null dependent_id as self', () => {
    it('never reassigns a null dependent_id document to activePatId', async () => {
      // Simulate backend returning a document with dependent_id: null during refreshDocuments for child
      api.getUserDocuments.mockImplementation(() => Promise.resolve([
        { id: 'doc-self-1', filename: 'self_blood_work.pdf', title: 'Self Blood Work', dependent_id: null },
      ]));

      render(
        <MemoryRouter>
          <ChatApp />
        </MemoryRouter>
      );

      await waitFor(() => {
        expect(screen.getByText('Self Blood Work')).toBeInTheDocument();
      });

      // Switch to Child
      const trigger = screen.getByTestId('patient-switcher-trigger');
      fireEvent.click(trigger);
      const childOption = await screen.findByText('Child Patient');
      fireEvent.click(childOption.closest('button'));

      await waitFor(() => {
        expect(api.getUserDocuments).toHaveBeenCalledWith('dep-child-1');
      });

      // Wait a moment for state updates
      await new Promise((r) => setTimeout(r, 200));

      // Bug verification: If docPat incorrectly defaulted to activePatId ('dep-child-1'),
      // then 'Self Blood Work' will leak and be visible in Child's conversation list.
      // It MUST NOT be in the document list.
      expect(screen.queryByText('Self Blood Work')).not.toBeInTheDocument();
    });
  });

  describe('Regression: getDocumentChats forwards patient_id', () => {
    it('appends patient_id query param when fetching standalone chat messages for a dependent', async () => {
      const actualApi = await vi.importActual('../services/api');
      const originalFetch = globalThis.fetch;
      const fetchSpy = vi.fn().mockResolvedValue({
        ok: true,
        json: () => Promise.resolve([{ id: 'msg-1', message: 'Hello Child', role: 'user' }]),
      });
      globalThis.fetch = fetchSpy;
      try {
        await actualApi.getDocumentChats(null, 'session-child-1', 'dep-child-1');
        expect(fetchSpy).toHaveBeenCalledWith(
          expect.stringContaining('/users/me/chats?session_id=session-child-1&patient_id=dep-child-1'),
          expect.any(Object)
        );
      } finally {
        globalThis.fetch = originalFetch;
      }
    });
  });

  describe('R2: Legacy cache sanitizer for getCachedConversations and getCachedDocuments', () => {
    it('sanitizes legacy conversations on read: pdf owner wins, untagged tagged with requested patientId, standalone preserves tag', async () => {
      const actualApi = await vi.importActual('../services/api');
      const stableUid = actualApi.getStableCacheUid();
      localStorage.clear();

      // (i) conversation tagged dep_a whose pdf says self
      const conv1 = {
        id: 'conv-1',
        title: 'Report Chat',
        patientId: 'dep_a',
        patient_id: 'dep_a',
        pdf: { id: 'doc-1', filename: 'report.pdf', patientId: 'self' },
        messages: [{ role: 'user', message: 'Hello' }],
      };

      // (ii) conversation with messages and no tag
      const conv2 = {
        id: 'conv-2',
        title: 'Untagged Chat',
        messages: [{ role: 'user', message: 'Untagged message' }],
      };

      // (iii) dep_a-tagged chat with no pdf
      const conv3 = {
        id: 'conv-3',
        title: 'Standalone Dep A Chat',
        patientId: 'dep_a',
        patient_id: 'dep_a',
        pdf: null,
        messages: [{ role: 'user', message: 'Dep A standalone' }],
      };

      // Seed localStorage
      localStorage.setItem(
        `mediskye_conversations_${stableUid}_dep_a`,
        JSON.stringify([conv1, conv3])
      );
      localStorage.setItem(
        `mediskye_conversations_${stableUid}_self`,
        JSON.stringify([conv2])
      );

      // (i) conv1 has pdf.patientId == 'self', so returned under 'self', NOT 'dep_a'
      const selfConvs = actualApi.getCachedConversations('self');
      expect(selfConvs.some((c) => c.id === 'conv-1')).toBe(true);
      const depAConvs = actualApi.getCachedConversations('dep_a');
      expect(depAConvs.some((c) => c.id === 'conv-1')).toBe(false);

      // (ii) conv2 had no tag and was read under 'self' -> tagged self, returned under self, NOT dep_a
      expect(selfConvs.some((c) => c.id === 'conv-2')).toBe(true);
      expect(depAConvs.some((c) => c.id === 'conv-2')).toBe(false);

      // (iii) conv3 is a standalone chat tagged dep_a -> returned under dep_a, NOT self
      expect(depAConvs.some((c) => c.id === 'conv-3')).toBe(true);
      expect(selfConvs.some((c) => c.id === 'conv-3')).toBe(false);
    });
  });
});
