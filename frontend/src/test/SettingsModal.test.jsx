import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import SettingsModal from '../components/SettingsModal';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getProfile: vi.fn().mockResolvedValue(null),
  updateProfile: vi.fn(),
  changePassword: vi.fn(),
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
  });

  it('renders account fields populated from currentUser', () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
      />
    );

    expect(screen.getByDisplayValue('Original Name')).toBeInTheDocument();
    expect(screen.getByDisplayValue('patient@example.com')).toBeInTheDocument();
    expect(screen.getByDisplayValue('1990-05-15')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Male')).toBeInTheDocument();
    expect(screen.getByDisplayValue('O+')).toBeInTheDocument();
  });

  it('optimistically updates and persists full_name on blur with success toast', async () => {
    const showToast = vi.fn();
    const onProfileUpdated = vi.fn();
    api.updateProfile.mockResolvedValueOnce({
      ...mockUser,
      full_name: 'Jane Smith',
    });

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
        showToast={showToast}
        onProfileUpdated={onProfileUpdated}
      />
    );

    const nameInput = screen.getByDisplayValue('Original Name');
    fireEvent.change(nameInput, { target: { value: 'Jane Smith' } });
    expect(nameInput.value).toBe('Jane Smith');

    fireEvent.blur(nameInput);

    await waitFor(() => {
      expect(api.updateProfile).toHaveBeenCalledWith({ full_name: 'Jane Smith' });
    });

    await waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('success', 'Changes Saved', expect.any(String));
      expect(onProfileUpdated).toHaveBeenCalledWith(expect.objectContaining({ full_name: 'Jane Smith' }));
    });
  });

  it('rolls back local field value and shows error toast when API fails', async () => {
    const showToast = vi.fn();
    api.updateProfile.mockRejectedValueOnce(new Error('Network error'));

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
        showToast={showToast}
      />
    );

    const nameInput = screen.getByDisplayValue('Original Name');
    fireEvent.change(nameInput, { target: { value: 'Failing Name' } });
    expect(nameInput.value).toBe('Failing Name');

    fireEvent.blur(nameInput);

    await waitFor(() => {
      expect(api.updateProfile).toHaveBeenCalledWith({ full_name: 'Failing Name' });
    });

    await waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('error', 'Update Failed', 'Network error');
      // Rollback to original value
      expect(nameInput.value).toBe('Original Name');
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
    const deleteBtn = screen.getByRole('button', { name: /delete account/i });
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

  it('wires change password modal to changePassword API and shows success toast on save', async () => {
    const showToast = vi.fn();
    api.changePassword.mockResolvedValueOnce({ message: 'Password changed successfully' });

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
      expect(api.changePassword).toHaveBeenCalledWith('OldPassword123!', 'NewPassword123!');
      expect(showToast).toHaveBeenCalledWith('success', 'Password Changed', expect.any(String));
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

    const select = screen.getByDisplayValue('English (US)');
    fireEvent.change(select, { target: { value: 'Spanish' } });

    expect(setLanguage).toHaveBeenCalledWith('Spanish');
    await waitFor(() => {
      expect(api.updateProfile).toHaveBeenCalledWith({ language_preference: 'Spanish' });
    });
    await waitFor(() => {
      expect(showToast).toHaveBeenCalledWith('success', 'Language Updated', expect.any(String));
      expect(onProfileUpdated).toHaveBeenCalledWith(expect.objectContaining({ language_preference: 'Spanish' }));
    });
  });

  it('persists the System theme preference without collapsing it to dark/light', () => {
    const setThemePreference = vi.fn();

    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        setDarkMode={vi.fn()}
        themePreference="light"
        setThemePreference={setThemePreference}
        currentUser={mockUser}
      />
    );

    fireEvent.click(screen.getByRole('button', { name: /system/i }));
    expect(setThemePreference).toHaveBeenCalledWith('system');
  });

  it('renders Change email and Privacy policy as disabled with tooltips', () => {
    render(
      <SettingsModal
        isOpen={true}
        onClose={vi.fn()}
        darkMode={false}
        currentUser={mockUser}
      />
    );

    const emailBtn = screen.getByRole('button', { name: /change email/i });
    expect(emailBtn).toBeDisabled();
    expect(emailBtn).toHaveAttribute('title', 'Coming soon — contact support to change your email');

    const privacyBtn = screen.getByRole('button', { name: /privacy policy/i });
    expect(privacyBtn).toBeDisabled();
    expect(privacyBtn).toHaveAttribute('title', 'Policy coming soon');
  });

  it('renders LLM Provider selector and saves preference to localStorage', () => {
    localStorage.removeItem('mediskye_llm_provider');
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

    const providerSelect = screen.getByDisplayValue('Gemini (default)');
    expect(providerSelect).toBeInTheDocument();

    fireEvent.change(providerSelect, { target: { value: 'agentrouter' } });
    expect(localStorage.getItem('mediskye_llm_provider')).toBe('agentrouter');
    expect(showToast).toHaveBeenCalledWith(
      'success',
      'Provider Updated',
      expect.stringContaining('Switched to Agent Router')
    );
  });
});
