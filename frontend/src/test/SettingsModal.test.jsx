import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import SettingsModal from '../components/SettingsModal';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  updateProfile: vi.fn(),
  deleteAccount: vi.fn(),
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
});
