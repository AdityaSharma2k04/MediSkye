import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import React from 'react';
import SettingsModal from '../components/SettingsModal';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getProfile: vi.fn().mockResolvedValue(null),
  updateProfile: vi.fn(),
  deleteAccount: vi.fn(),
  getMemoryStatus: vi.fn().mockResolvedValue({ memory_consent_granted: false, fact_count: 0 }),
  getMemoryFacts: vi.fn().mockResolvedValue([]),
  getFacts: vi.fn().mockResolvedValue([]),
  createFact: vi.fn(),
  updateFact: vi.fn(),
  deleteFact: vi.fn(),
  updateMemoryConsent: vi.fn(),
  clearAllMemoryFacts: vi.fn(),
}));

const {
  mockCredential,
  mockCredentialFn,
  mockReauthenticateWithCredential,
  mockReauthenticateWithPopup,
  mockUpdatePassword,
  mockAuth,
} = vi.hoisted(() => {
  const credential = { providerId: 'password', signInMethod: 'password' };
  return {
    mockCredential: credential,
    mockCredentialFn: vi.fn().mockReturnValue(credential),
    mockReauthenticateWithCredential: vi.fn().mockResolvedValue({}),
    mockReauthenticateWithPopup: vi.fn().mockResolvedValue({}),
    mockUpdatePassword: vi.fn().mockResolvedValue({}),
    mockAuth: {
      currentUser: {
        email: 'patient@example.com',
        providerData: [{ providerId: 'password' }],
      },
    },
  };
});

vi.mock('firebase/auth', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    EmailAuthProvider: {
      credential: (...args) => mockCredentialFn(...args),
    },
    GoogleAuthProvider: vi.fn().mockImplementation(() => ({
      setCustomParameters: vi.fn(),
    })),
    reauthenticateWithCredential: (...args) => mockReauthenticateWithCredential(...args),
    reauthenticateWithPopup: (...args) => mockReauthenticateWithPopup(...args),
    updatePassword: (...args) => mockUpdatePassword(...args),
  };
});

vi.mock('../services/firebase', async (importOriginal) => {
  const actual = await importOriginal();
  return {
    ...actual,
    auth: mockAuth,
  };
});

describe('SettingsModal Account fields & Deletion', () => {
  const mockUser = {
    email: 'patient@example.com',
    full_name: 'Original Name',
    date_of_birth: '1990-05-15',
    biological_sex: 'Male',
    blood_type: 'O+',
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockAuth.currentUser = {
      email: 'patient@example.com',
      providerData: [{ providerId: 'password' }],
    };
  });

  it('renders Manage Health Profile & Caregivers button which triggers onOpenProfile and closes modal', async () => {
    const onOpenProfile = vi.fn();
    const onClose = vi.fn();
    render(
      <SettingsModal
        isOpen={true}
        onClose={onClose}
        darkMode={false}
        currentUser={mockUser}
        onOpenProfile={onOpenProfile}
      />
    );

    const profileBtn = await screen.findByRole('button', { name: /manage health profile & caregivers/i });
    expect(profileBtn).toBeInTheDocument();
    fireEvent.click(profileBtn);
    expect(onClose).toHaveBeenCalled();
    expect(onOpenProfile).toHaveBeenCalled();
  });

  it('does not render redundant account form fields in Settings modal', async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
      />
    );

    await screen.findByRole('button', { name: /manage health profile & caregivers/i });
    expect(screen.queryByPlaceholderText('Your full name')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('Original Name')).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue('1990-05-15')).not.toBeInTheDocument();
  });

  it('updates draft state on change and persists preferences only after clicking Save Changes button', async () => {
    const showToast = vi.fn();
    const setLanguage = vi.fn();
    const onProfileUpdated = vi.fn();
    api.updateProfile.mockResolvedValueOnce({ ...mockUser, language_preference: 'Spanish' });

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
        language="English"
        setLanguage={setLanguage}
        showToast={showToast}
        onProfileUpdated={onProfileUpdated}
      />
    );

    const select = screen.getByLabelText(/AI Response Language/i);
    fireEvent.change(select, { target: { value: 'Spanish' } });

    // API should NOT be called before clicking Save Changes
    expect(api.updateProfile).not.toHaveBeenCalled();

    const saveBtn = screen.getByRole('button', { name: 'Save Changes' });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.updateProfile).toHaveBeenCalledWith({ language_preference: 'Spanish' });
      expect(setLanguage).toHaveBeenCalledWith('Spanish');
      expect(showToast).not.toHaveBeenCalled();
      expect(onProfileUpdated).toHaveBeenCalledWith(expect.objectContaining({ language_preference: 'Spanish' }));
    });
  });

  it('shows inline error alert when Save Changes fails', async () => {
    api.updateProfile.mockRejectedValueOnce(new Error('Network error'));

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
        language="English"
      />
    );

    const select = screen.getByLabelText(/AI Response Language/i);
    fireEvent.change(select, { target: { value: 'Spanish' } });

    const saveBtn = screen.getByRole('button', { name: 'Save Changes' });
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Network error');
    });
  });

  it('delete account confirmation modal enables button only when email is typed', async () => {
    const onDeleteAccount = vi.fn();

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
        onDeleteAccount={onDeleteAccount}
      />
    );

    // Click "Delete account" in settings modal
    const deleteBtn = await screen.findByRole('button', { name: /delete account/i });
    fireEvent.click(deleteBtn);

    // Confirmation dialog should be visible
    expect(screen.getByText('Delete your account?')).toBeInTheDocument();

    const confirmActionBtn = screen.getByRole('button', { name: 'Delete my account' });
    expect(confirmActionBtn).toBeDisabled();

    // Type incorrect email
    const input = screen.getByPlaceholderText('patient@example.com');
    fireEvent.change(input, { target: { value: 'wrong@example.com' } });
    expect(confirmActionBtn).toBeDisabled();

    // Type correct email
    fireEvent.change(input, { target: { value: 'patient@example.com' } });
    expect(confirmActionBtn).toBeEnabled();

    // Confirm deletion
    fireEvent.click(confirmActionBtn);
    expect(onDeleteAccount).toHaveBeenCalledTimes(1);
  });

  it('fetches profile and facts on modal open, asserts toggle shows correct state and facts list renders', async () => {
    const mockFacts = [
      { id: 'fact-1', fact_type: 'condition', fact_text: 'Asthma diagnosed 2020', confidence: 1.0, is_user_verified: true, source_type: 'user_edit' },
      { id: 'fact-2', fact_type: 'allergy', fact_text: 'Penicillin allergy', confidence: 1.0, is_user_verified: true, source_type: 'user_edit' },
    ];
    api.getProfile.mockResolvedValueOnce({
      ...mockUser,
      memory_consent_granted: true,
      diet_type: 'vegan',
      activity_level: 'moderate',
    });
    api.getMemoryFacts.mockResolvedValueOnce(mockFacts);

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={null}
      />
    );

    // Verify GET /users/me and GET /users/me/facts were called
    await waitFor(() => {
      expect(api.getProfile).toHaveBeenCalled();
      expect(api.getMemoryFacts).toHaveBeenCalled();
    });

    // Memory toggle should show 'Active'
    await waitFor(() => {
      expect(screen.getByText('Active')).toBeInTheDocument();
    });

    // Facts list should render facts
    expect(screen.getByText('Asthma diagnosed 2020')).toBeInTheDocument();
    expect(screen.getByText('Penicillin allergy')).toBeInTheDocument();
  });

  it('wires change password modal to Firebase auth and shows success toast on save', async () => {
    const showToast = vi.fn();

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
        showToast={showToast}
      />
    );

    // Open change password submodal
    const changePwdBtn = screen.getByRole('button', { name: /change password/i });
    expect(changePwdBtn).toBeEnabled();
    fireEvent.click(changePwdBtn);

    expect(screen.getByRole('dialog', { name: /change password/i })).toBeInTheDocument();

    const currentInput = screen.getByLabelText('Current password');
    const newInput = screen.getByLabelText('New password');
    const confirmInput = screen.getByLabelText('Confirm new password');

    fireEvent.change(currentInput, { target: { value: 'OldPassword123!' } });
    fireEvent.change(newInput, { target: { value: 'NewPassword123!' } });
    fireEvent.change(confirmInput, { target: { value: 'NewPassword123!' } });

    const saveBtn = screen.getByRole('button', { name: 'Save' });
    expect(saveBtn).toBeEnabled();
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(mockCredentialFn).toHaveBeenCalledWith('patient@example.com', 'OldPassword123!');
      expect(mockReauthenticateWithCredential).toHaveBeenCalledWith(mockAuth.currentUser, mockCredential);
      expect(mockUpdatePassword).toHaveBeenCalledWith(mockAuth.currentUser, 'NewPassword123!');
    });
  });

  it('allows Google OAuth users without a password to set a password', async () => {
    mockAuth.currentUser = {
      email: 'google_patient@example.com',
      providerData: [{ providerId: 'google.com' }],
    };

    const onClose = vi.fn();
    render(
      <SettingsModal
        isOpen={true}
        onClose={onClose}
        darkMode={false}
        currentUser={mockUser}
      />
    );

    const setPwdBtn = await screen.findByRole('button', { name: /set password/i });
    expect(setPwdBtn).toBeEnabled();
    expect(
      screen.getByText("You signed in with Google. You can set a password to enable email & password sign-in.")
    ).toBeInTheDocument();

    // Clicking enabled button opens modal with 'Set Password'
    fireEvent.click(setPwdBtn);
    const dialog = screen.getByRole('dialog', { name: /set password/i });
    expect(dialog).toBeInTheDocument();
    expect(within(dialog).queryByLabelText('Current password')).not.toBeInTheDocument();

    const newInput = within(dialog).getByLabelText('New password');
    const confirmInput = within(dialog).getByLabelText('Confirm new password');

    fireEvent.change(newInput, { target: { value: 'GoogleSet123!' } });
    fireEvent.change(confirmInput, { target: { value: 'GoogleSet123!' } });

    const submitBtn = within(dialog).getByRole('button', { name: 'Set password' });
    expect(submitBtn).toBeEnabled();
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockUpdatePassword).toHaveBeenCalledWith(mockAuth.currentUser, 'GoogleSet123!');
    });
  });

  it('prompts re-authentication with Google popup if updatePassword throws auth/requires-recent-login', async () => {
    mockAuth.currentUser = {
      email: 'google_patient@example.com',
      providerData: [{ providerId: 'google.com' }],
    };

    const recentLoginErr = new Error('Requires recent login');
    recentLoginErr.code = 'auth/requires-recent-login';
    mockUpdatePassword.mockRejectedValueOnce(recentLoginErr).mockResolvedValueOnce({});

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
      />
    );

    const setPwdBtn = await screen.findByRole('button', { name: /set password/i });
    fireEvent.click(setPwdBtn);

    const dialog = screen.getByRole('dialog', { name: /set password/i });
    const newInput = within(dialog).getByLabelText('New password');
    const confirmInput = within(dialog).getByLabelText('Confirm new password');

    fireEvent.change(newInput, { target: { value: 'GoogleSet123!' } });
    fireEvent.change(confirmInput, { target: { value: 'GoogleSet123!' } });

    const submitBtn = within(dialog).getByRole('button', { name: 'Set password' });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(mockReauthenticateWithPopup).toHaveBeenCalledWith(mockAuth.currentUser, expect.anything());
      expect(mockUpdatePassword).toHaveBeenCalledTimes(2);
    });
  });

  it('persists the language preference via updateProfile', async () => {
    const showToast = vi.fn();
    const setLanguage = vi.fn();
    const onProfileUpdated = vi.fn();
    api.updateProfile.mockResolvedValueOnce({ ...mockUser, language_preference: 'Spanish' });

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
        language="English"
        setLanguage={setLanguage}
        showToast={showToast}
        onProfileUpdated={onProfileUpdated}
      />
    );

    const select = screen.getByLabelText(/AI Response Language/i);
    fireEvent.change(select, { target: { value: 'Spanish' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save Changes' }));

    await waitFor(() => {
      expect(api.updateProfile).toHaveBeenCalledWith({ language_preference: 'Spanish' });
      expect(setLanguage).toHaveBeenCalledWith('Spanish');
      expect(showToast).not.toHaveBeenCalled();
      expect(onProfileUpdated).toHaveBeenCalledWith(expect.objectContaining({ language_preference: 'Spanish' }));
    });
  });

  it('does not render theme selector in Settings modal', async () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
      />
    );

    await screen.findByRole('button', { name: /save changes/i });
    expect(screen.queryByRole('button', { name: /system/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^dark$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^light$/i })).not.toBeInTheDocument();
  });

  it('shows unsaved changes warning when attempting to close with dirty state and allows discarding', async () => {
    const onClose = vi.fn();

    render(
      <SettingsModal
        isOpen={true}
        onClose={onClose}
        darkMode={false}
        currentUser={mockUser}
        language="English"
      />
    );

    // Initial state: clicking Close closes immediately
    const closeBtn = await screen.findByRole('button', { name: 'Close settings' });
    fireEvent.click(closeBtn);
    expect(onClose).toHaveBeenCalledTimes(1);

    onClose.mockClear();

    // Modify a field to create dirty state
    const select = screen.getByLabelText(/AI Response Language/i);
    fireEvent.change(select, { target: { value: 'French' } });

    // Try to close via X button
    fireEvent.click(closeBtn);

    // onClose should NOT have been called yet
    expect(onClose).not.toHaveBeenCalled();

    // Confirm dialog should appear
    expect(screen.getByText('Unsaved Changes')).toBeInTheDocument();
    expect(
      screen.getByText('You have unsaved changes. Are you sure you want to discard them?')
    ).toBeInTheDocument();

    // Click "Keep Editing"
    const keepEditingBtn = screen.getByRole('button', { name: 'Keep Editing' });
    fireEvent.click(keepEditingBtn);
    expect(screen.queryByText('Unsaved Changes')).not.toBeInTheDocument();
    expect(onClose).not.toHaveBeenCalled();

    // Try to close again via Cancel button
    const cancelBtn = screen.getByRole('button', { name: 'Cancel' });
    fireEvent.click(cancelBtn);

    expect(screen.getByText('Unsaved Changes')).toBeInTheDocument();

    // Click "Discard Changes"
    const discardBtn = screen.getByRole('button', { name: 'Discard Changes' });
    fireEvent.click(discardBtn);

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('renders Privacy policy as an active link in About section that closes modal on click', async () => {
    const onClose = vi.fn();
    render(
      <SettingsModal
        isOpen={true}
        onClose={onClose}
        darkMode={false}
        currentUser={mockUser}
      />
    );

    const privacyLink = await screen.findByRole('link', { name: /privacy policy/i });
    expect(privacyLink).toBeInTheDocument();
    expect(privacyLink).toHaveAttribute('href', '/privacy');

    fireEvent.click(privacyLink);
    expect(onClose).toHaveBeenCalled();
  });
});
