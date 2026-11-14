import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ExternalAuthLanding from '../components/ExternalAuthLanding';
import Workbench from '../components/workbench/Workbench';

// Mock Firebase services
vi.mock('../services/firebase', async (importOriginal) => {
  const actual = await importOriginal();
  const mockSignInWithPopup = vi.fn().mockResolvedValue({
    user: {
      email: 'alex@example.com',
      getIdToken: vi.fn().mockResolvedValue('fake-id-token-123'),
    },
  });
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
    signInWithPopup: mockSignInWithPopup,
    onAuthStateChanged: vi.fn(),
    getFirebaseErrorMessage: vi.fn((err) => err?.message || 'Error'),
  };
});

describe('ExternalAuthLanding & Native Browser Auth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.fetch = vi.fn().mockResolvedValue({ ok: true });
  });

  it('renders Google sign-in button without auto-invoking signInWithPopup on mount', async () => {
    const { signInWithPopup } = await import('../services/firebase');
    render(<ExternalAuthLanding />);

    // Should NOT have called popup on initial render
    expect(signInWithPopup).not.toHaveBeenCalled();

    // Renders primary button with proper prompt
    const button = screen.getByRole('button', { name: /continue with google account/i });
    expect(button).toBeInTheDocument();
  });

  it('calls signInWithPopup on button click and reports credentials to native loopback', async () => {
    const { signInWithPopup } = await import('../services/firebase');
    render(<ExternalAuthLanding />);

    const button = screen.getByRole('button', { name: /continue with google account/i });
    fireEvent.click(button);

    await waitFor(() => {
      expect(signInWithPopup).toHaveBeenCalledTimes(1);
    });

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/__native_auth_done?id_token='),
        expect.objectContaining({ method: 'GET' })
      );
    });

    await waitFor(() => {
      const fallbackLink = screen.getByRole('link', { name: /open mediskye app/i });
      expect(fallbackLink).toBeInTheDocument();
      expect(fallbackLink).toHaveAttribute('href', expect.stringContaining('/__native_auth_done?id_token='));
    });
  });
});

describe('Workbench Header Cloud Sync Reload Button', () => {
  it('renders Cloud Sync button near Search and triggers onManualSync when clicked', () => {
    const onManualSync = vi.fn();
    render(
      <Workbench
        isDesktop={true}
        viewMode="chat"
        onViewModeChange={vi.fn()}
        onManualSync={onManualSync}
        isSyncing={false}
        currentUser={{ id: 'u1', email: 'u1@test.com' }}
        dependents={[]}
        selectedPatientId="self"
        onSelectPatient={() => {}}
        messages={[]}
        conversations={[]}
        onOpenPalette={() => {}}
        onToggleInspector={() => {}}
      />
    );

    const syncButton = screen.getByLabelText(/sync latest chats and reports from cloud/i);
    expect(syncButton).toBeInTheDocument();
    expect(syncButton).toHaveAttribute('title', 'Sync latest chats & reports from cloud');

    fireEvent.click(syncButton);
    expect(onManualSync).toHaveBeenCalledTimes(1);
  });
});
