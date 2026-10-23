import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import AuthAction from '../components/AuthAction';

const mockApplyActionCode = vi.fn();
const mockVerifyPasswordResetCode = vi.fn();
const mockConfirmPasswordReset = vi.fn();

vi.mock('../services/firebase', () => ({
  auth: {},
  applyActionCode: (...args) => mockApplyActionCode(...args),
  verifyPasswordResetCode: (...args) => mockVerifyPasswordResetCode(...args),
  confirmPasswordReset: (...args) => mockConfirmPasswordReset(...args),
  getFirebaseErrorMessage: () => 'Authentication failed. Please try again.',
}));

const renderAction = (query) => render(
  <MemoryRouter initialEntries={[`/auth/action${query}`]}>
    <AuthAction />
  </MemoryRouter>
);

describe('AuthAction', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockApplyActionCode.mockResolvedValue(undefined);
    mockVerifyPasswordResetCode.mockResolvedValue('patient@example.com');
    mockConfirmPasswordReset.mockResolvedValue(undefined);
  });

  it('applies an email verification code and shows the login success message', async () => {
    renderAction('?mode=verifyEmail&oobCode=verify-code');

    await waitFor(() => {
      expect(mockApplyActionCode).toHaveBeenCalledWith({}, 'verify-code');
    });
    expect(await screen.findByText('Email Verified! You can now log in.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Go to Login' })).toHaveAttribute('href', '/login');
  });

  it('shows a clear error when a verification code is expired', async () => {
    mockApplyActionCode.mockRejectedValue({ code: 'auth/expired-action-code' });
    renderAction('?mode=verifyEmail&oobCode=expired-code');

    expect(await screen.findByRole('alert')).toHaveTextContent(/invalid or has expired/i);
  });

  it('checks a reset code and confirms the new password', async () => {
    renderAction('?mode=resetPassword&oobCode=reset-code');

    const newPasswordInput = await screen.findByLabelText('New Password');
    const confirmPasswordInput = screen.getByLabelText('Confirm Password');
    expect(newPasswordInput).toHaveProperty('minLength', 8);
    expect(confirmPasswordInput).toHaveProperty('minLength', 8);
    expect(mockVerifyPasswordResetCode).toHaveBeenCalledWith({}, 'reset-code');

    fireEvent.change(newPasswordInput, { target: { value: 'StrongPass123!' } });
    fireEvent.change(confirmPasswordInput, { target: { value: 'StrongPass123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    await waitFor(() => {
      expect(mockConfirmPasswordReset).toHaveBeenCalledWith({}, 'reset-code', 'StrongPass123!');
    });
    expect(await screen.findByText(/password has been reset successfully/i)).toBeInTheDocument();
  });

  it('rejects mismatched new passwords without calling Firebase', async () => {
    renderAction('?mode=resetPassword&oobCode=reset-code');

    await screen.findByLabelText('New Password');
    fireEvent.change(screen.getByLabelText('New Password'), { target: { value: 'StrongPass123!' } });
    fireEvent.change(screen.getByLabelText('Confirm Password'), { target: { value: 'DifferentPass123!' } });
    fireEvent.click(screen.getByRole('button', { name: 'Reset Password' }));

    expect(await screen.findByRole('alert')).toHaveTextContent('Passwords do not match.');
    expect(mockConfirmPasswordReset).not.toHaveBeenCalled();
  });

  it('rejects unknown action modes', async () => {
    renderAction('?mode=unknown&oobCode=code');
    expect(await screen.findByRole('alert')).toHaveTextContent(/not supported/i);
  });

  it('rejects links without a code', async () => {
    renderAction('?mode=verifyEmail');
    expect(await screen.findByRole('alert')).toHaveTextContent(/missing its verification code/i);
  });
});
