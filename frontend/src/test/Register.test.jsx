import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import Register, { validatePassword, getPasswordStrength } from '../components/Register';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockCreateUserWithEmailAndPassword = vi.fn();
const mockUpdateProfile = vi.fn();
const mockSignInWithPopup = vi.fn();
const mockSendEmailVerification = vi.fn();
const mockSignOut = vi.fn();
const mockApiPost = vi.fn();

vi.mock('../services/api', () => ({
  default: {
    post: (...args) => mockApiPost(...args),
  },
  api: {
    post: (...args) => mockApiPost(...args),
  },
}));

vi.mock('../services/firebase', async () => {
  const actual = await vi.importActual('../services/firebase');
  return {
    ...actual,
    auth: {},
    googleProvider: {},
    createUserWithEmailAndPassword: (...args) => mockCreateUserWithEmailAndPassword(...args),
    updateProfile: (...args) => mockUpdateProfile(...args),
    signInWithPopup: (...args) => mockSignInWithPopup(...args),
    sendEmailVerification: (...args) => mockSendEmailVerification(...args),
    signOut: (...args) => mockSignOut(...args),
  };
});

describe('Register Component with Firebase Auth', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockApiPost.mockResolvedValue({ message: 'Verification email sent' });
  });

  it('renders initial step with email input and continue button', () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    expect(screen.getByPlaceholderText(/email address/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /continue/i })).toBeInTheDocument();
  });

  it('validates email format before advancing to password step (rejecting notanemail and test@test)', () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    const emailInput = screen.getByPlaceholderText(/email address/i);
    const continueBtn = screen.getByRole('button', { name: /continue/i });

    // Invalid email without domain
    fireEvent.change(emailInput, { target: { value: 'notanemail' } });
    fireEvent.submit(continueBtn.closest('form'));

    expect(screen.getByText(/please enter a valid email address \(e\.g\., name@example\.com\)\./i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/create a password/i)).not.toBeInTheDocument();

    // Invalid email without top-level domain (test@test)
    fireEvent.change(emailInput, { target: { value: 'test@test' } });
    fireEvent.submit(continueBtn.closest('form'));

    expect(screen.getByText(/please enter a valid email address \(e\.g\., name@example\.com\)\./i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/create a password/i)).not.toBeInTheDocument();
  });

  it('validates password constraints with NIST 800-63B standards and strength meter', () => {
    // 1. Passwords without numbers/symbols are accepted
    expect(validatePassword('blue coffee morning')).toBeNull();
    expect(validatePassword('simplepass')).toBeNull();
    expect(validatePassword('ValidPass123')).toBeNull();

    // 2. Short passwords (< 8 chars) are rejected
    expect(validatePassword('short')).toBe('Password must be at least 8 characters.');
    expect(validatePassword('')).toBe('Password must be at least 8 characters.');

    // 3. Common weak passwords and repeated characters are rejected
    expect(validatePassword('12345678')).toBe('This password is too common. Please choose a stronger one.');
    expect(validatePassword('password')).toBe('This password is too common. Please choose a stronger one.');
    expect(validatePassword('123456789')).toBe('This password is too common. Please choose a stronger one.');
    expect(validatePassword('qwerty123')).toBe('This password is too common. Please choose a stronger one.');
    expect(validatePassword('qwertyui')).toBe('This password is too common. Please choose a stronger one.');
    expect(validatePassword('mediskye')).toBe('This password is too common. Please choose a stronger one.');
    expect(validatePassword('aaaaaaaa')).toBe('This password is too common. Please choose a stronger one.');

    // 4. Over 64 chars rejected
    expect(validatePassword('a'.repeat(65))).toBe('Password cannot exceed 64 characters.');

    // Strength levels (weak: red, fair: amber, strong: emerald)
    expect(getPasswordStrength('12345678').level).toBe('weak');
    expect(getPasswordStrength('simplepass').level).toBe('fair');
    expect(getPasswordStrength('blue coffee morning').level).toBe('strong');
  });

  it('shows error if password is under 8 characters', async () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1: enter valid email
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    // Step 2: enter 6 character password
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: '123456' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: '123456' } });
    
    // Check consent
    const consentInput = document.getElementById('register-phi-consent');
    fireEvent.click(consentInput);

    // Submit
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument();
    expect(mockCreateUserWithEmailAndPassword).not.toHaveBeenCalled();
  });

  it('accepts passwords without numbers/symbols (e.g., blue coffee morning and simplepass)', async () => {
    const mockUser = {
      email: 'user@example.com',
      getIdToken: vi.fn().mockResolvedValue('mock_token_passphrase'),
    };
    mockCreateUserWithEmailAndPassword.mockResolvedValueOnce({ user: mockUser });
    mockSendEmailVerification.mockResolvedValueOnce();
    mockSignOut.mockResolvedValueOnce();

    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1: enter valid email
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    // Step 2: enter natural passphrase without numbers or symbols
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: 'blue coffee morning' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: 'blue coffee morning' } });
    fireEvent.click(document.getElementById('register-phi-consent'));
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(mockCreateUserWithEmailAndPassword).toHaveBeenCalledWith(
        expect.anything(),
        'user@example.com',
        'blue coffee morning'
      );
      expect(mockApiPost).toHaveBeenCalledWith('/auth/send-custom-verification', { email: 'user@example.com' });
    });
  });

  it('rejects common weak passwords like 12345678 and password', async () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1: enter valid email
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    // Step 2: attempt 12345678
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: '12345678' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: '12345678' } });
    fireEvent.click(document.getElementById('register-phi-consent'));
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(screen.getByText(/this password is too common/i)).toBeInTheDocument();
    expect(mockCreateUserWithEmailAndPassword).not.toHaveBeenCalled();

    // Attempt 'password'
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: 'password' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: 'password' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(screen.getByText(/this password is too common/i)).toBeInTheDocument();
    expect(mockCreateUserWithEmailAndPassword).not.toHaveBeenCalled();
  });

  it('real-time password match validation: displays inline error, disables submit button, and re-enables on match', async () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1: Advance to password step
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    const passwordInput = screen.getByPlaceholderText(/create a password/i);
    const confirmInput = screen.getByPlaceholderText(/confirm password/i);
    const submitBtn = screen.getByRole('button', { name: /create account/i });

    // Initially, confirm password is empty -> no error
    expect(screen.queryByText(/passwords do not match/i)).not.toBeInTheDocument();
    expect(confirmInput).not.toHaveClass('border-red-500');

    // Enter valid password
    fireEvent.change(passwordInput, { target: { value: 'validPassword123' } });

    // 1. Typing mismatched confirm password immediately shows inline error and red border
    fireEvent.change(confirmInput, { target: { value: 'mismatch123' } });
    expect(screen.getByText(/passwords do not match\./i)).toBeInTheDocument();
    expect(confirmInput).toHaveClass('border-red-500');

    // 2. Submit button is disabled
    expect(submitBtn).toBeDisabled();

    // 3. Button re-enables and error clears when passwords match
    fireEvent.change(confirmInput, { target: { value: 'validPassword123' } });
    expect(screen.queryByText(/passwords do not match/i)).not.toBeInTheDocument();
    expect(confirmInput).not.toHaveClass('border-red-500');
    expect(submitBtn).not.toBeDisabled();
  });

  it('shows error if password and confirm password do not match on submit fallback', async () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    // Step 2: mismatch passwords
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: 'validPassword123' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: 'mismatchPassword456' } });
    fireEvent.click(document.getElementById('register-phi-consent'));

    const submitBtn = screen.getByRole('button', { name: /create account/i });
    expect(submitBtn).toBeDisabled();

    // Trigger form submit directly (e.g. pressing Enter)
    fireEvent.submit(submitBtn.closest('form'));

    expect(screen.getAllByText(/passwords do not match/i).length).toBeGreaterThanOrEqual(1);
    expect(mockCreateUserWithEmailAndPassword).not.toHaveBeenCalled();
  });

  it('shows error if PHI consent is not checked', async () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    // Step 2: valid password but no consent
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: 'validPassword123' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: 'validPassword123' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(screen.getByText(/you must consent to phi processing/i)).toBeInTheDocument();
    expect(mockCreateUserWithEmailAndPassword).not.toHaveBeenCalled();
  });

  it('calls createUserWithEmailAndPassword, sends email verification, signs out, and shows verification banner', async () => {
    const mockUser = {
      email: 'user@example.com',
      getIdToken: vi.fn().mockResolvedValue('mock_register_token_789'),
    };
    mockCreateUserWithEmailAndPassword.mockResolvedValueOnce({ user: mockUser });
    mockSendEmailVerification.mockResolvedValueOnce();
    mockSignOut.mockResolvedValueOnce();

    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1: enter email with whitespace
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: '  user@example.com  ' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    // Step 2: enter valid password and matching confirm password and check consent
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: 'validPassword123' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: 'validPassword123' } });
    const consentInput = document.getElementById('register-phi-consent');
    fireEvent.click(consentInput);

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(mockCreateUserWithEmailAndPassword).toHaveBeenCalledWith(expect.anything(), 'user@example.com', 'validPassword123');
      expect(mockSendEmailVerification).toHaveBeenCalled();
      expect(mockApiPost).toHaveBeenCalledWith('/auth/send-custom-verification', { email: 'user@example.com' });
      expect(mockSignOut).not.toHaveBeenCalled();
      expect(localStorage.getItem('token')).toBeNull();
    });

    expect(screen.getByText(/account created! we've sent a verification link to user@example\.com\. please check your inbox\./i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /go to login/i })).toBeInTheDocument();
  });

  it('syncs display name with updateProfile when full name is provided', async () => {
    const mockUser = {
      email: 'user@example.com',
      getIdToken: vi.fn().mockResolvedValue('mock_token_with_name'),
    };
    mockCreateUserWithEmailAndPassword.mockResolvedValueOnce({ user: mockUser });
    mockUpdateProfile.mockResolvedValueOnce();
    mockSignOut.mockResolvedValueOnce();

    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    fireEvent.change(screen.getByPlaceholderText(/full name/i), { target: { value: 'Jane Doe' } });
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: 'validPassword123' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: 'validPassword123' } });
    fireEvent.click(document.getElementById('register-phi-consent'));

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(mockUpdateProfile).toHaveBeenCalledWith(mockUser, { displayName: 'Jane Doe' });
      expect(mockSendEmailVerification).toHaveBeenCalled();
      expect(mockApiPost).toHaveBeenCalledWith('/auth/send-custom-verification', { email: 'user@example.com' });
      expect(mockSignOut).not.toHaveBeenCalled();
    });
  });

  it('displays mapped auth/email-already-in-use error message clearly', async () => {
    const err = new Error('Email exists');
    err.code = 'auth/email-already-in-use';
    mockCreateUserWithEmailAndPassword.mockRejectedValueOnce(err);

    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    // Step 2
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: 'validPassword123' } });
    fireEvent.change(screen.getByPlaceholderText(/confirm password/i), { target: { value: 'validPassword123' } });
    fireEvent.click(document.getElementById('register-phi-consent'));
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText(/an account with this email already exists\. please log in or reset your password\./i)).toBeInTheDocument();
    });
  });
});
