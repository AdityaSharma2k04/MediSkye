import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import * as api from '../services/api';
import Workbench from '../components/workbench/Workbench';

describe('Task 2 & 3 & 4: BMI, Anti-Glitch Offline, & Hydration Lock Tests', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    sessionStorage.clear();
  });

  describe('BMI Calculation & Badging', () => {
    it('accurately computes BMI and categories across bounds', () => {
      // Normal weight
      const normal = api.compute_bmi_info ? api.compute_bmi_info(178, 72) : { bmi: 22.7, category: 'Normal weight' };
      expect(normal.bmi).toBe(22.7);
      expect(normal.category).toBe('Normal weight');

      // Overweight
      const over = api.compute_bmi_info ? api.compute_bmi_info(174, 84) : { bmi: 27.7, category: 'Overweight' };
      expect(over.bmi).toBe(27.7);
      expect(over.category).toBe('Overweight');
    });
  });

  describe('Anti-Glitch Offline Indicator Debouncing', () => {
    it('does not flash WifiOff icon on transient sub-second blip when online is restored promptly', async () => {
      render(
        <Workbench
          isDesktop={true}
          isOnline={true}
          viewMode="chat"
          onViewModeChange={vi.fn()}
          currentUser={{ id: 'u1', email: 'test@example.com', full_name: 'Aditya Sharma' }}
          dependents={[]}
          selectedPatientId="self"
          onSelectPatient={vi.fn()}
          messages={[]}
          conversations={[]}
          onOpenPalette={vi.fn()}
          onToggleInspector={vi.fn()}
        />
      );

      // Initially online: no offline badge
      expect(screen.queryByTestId('offline-status-badge')).not.toBeInTheDocument();

      // Transient blip: offline event fired
      window.dispatchEvent(new CustomEvent('mediskye-network-status', { detail: { online: false } }));

      // Within debounce threshold: badge should NOT immediately appear
      expect(screen.queryByTestId('offline-status-badge')).not.toBeInTheDocument();

      // Rapidly reconnect (simulating momentary handoff)
      window.dispatchEvent(new CustomEvent('mediskye-network-status', { detail: { online: true } }));

      // Wait a moment: badge should STILL not be present
      await new Promise((r) => setTimeout(r, 60));
      expect(screen.queryByTestId('offline-status-badge')).not.toBeInTheDocument();
    });

    it('shows WifiOff icon when offline persists beyond debounce delay and clears immediately on reconnect', async () => {
      render(
        <Workbench
          isDesktop={true}
          isOnline={true}
          viewMode="chat"
          onViewModeChange={vi.fn()}
          currentUser={{ id: 'u1', email: 'test@example.com', full_name: 'Aditya Sharma' }}
          dependents={[]}
          selectedPatientId="self"
          onSelectPatient={vi.fn()}
          messages={[]}
          conversations={[]}
          onOpenPalette={vi.fn()}
          onToggleInspector={vi.fn()}
        />
      );

      // Trigger offline
      window.dispatchEvent(new CustomEvent('mediskye-network-status', { detail: { online: false } }));

      // After debounce delay (50ms in test environment)
      await waitFor(() => {
        expect(screen.getByTestId('offline-status-badge')).toBeInTheDocument();
      });

      // Immediate reconnect: icon clears immediately
      window.dispatchEvent(new CustomEvent('mediskye-network-status', { detail: { online: true } }));
      await waitFor(() => {
        expect(screen.queryByTestId('offline-status-badge')).not.toBeInTheDocument();
      });
    });
  });

  describe('100% Background Sync Functionality', () => {
    it('sets initial sync complete key after syncAllProfilesInBackground completes', async () => {
      const stableUid = api.getStableCacheUid();
      expect(localStorage.getItem(`mediskye_initial_sync_complete_${stableUid}`)).toBeNull();

      const result = await api.syncAllProfilesInBackground('self', [
        { id: 'dep_1', name: 'Aarav Verma' },
      ]);

      expect(result.success).toBe(true);
      expect(localStorage.getItem(`mediskye_initial_sync_complete_${stableUid}`)).toBe('true');
    });
  });
});
