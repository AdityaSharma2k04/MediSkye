import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import Login from '../components/Login';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockSignInWithPopup = vi.fn();
const mockSignInWithEmailAndPassword = vi.fn();
const mockSendPasswordResetEmail = vi.fn();
const mockSignOut = vi.fn();
const mockApiPost = vi.fn();

vi.mock('../services/api', () => ({
  default: {
    post: (...args) => mockApiPost(...args),
  },
  api: {
    post: (...args) => mockApiPost(...args),
  },
  sendCustomPasswordReset: (...args) => mockApiPost('/auth/send-custom-password-reset', { email: args[0] }),
  sendCustomVerification: (...args) => mockApiPost('/auth/send-custom-verification', { email: args[0] }),
}));

vi.mock('../services/firebase', async () => {
  const actual = await vi.importActual('../services/firebase');
  return {
    ...actual,
    auth: {},
    googleProvider: {},
    signInWithPopup: (...args) => mockSignInWithPopup(...args),
    signInWithEmailAndPassword: (...args) => mockSignInWithEmailAndPassword(...args),
    sendPasswordResetEmail: (...args) => mockSendPasswordResetEmail(...args),
    signOut: (...args) => mockSignOut(...args),
  };
});

describe('Login Component with Firebase Auth & Password Reset', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    mockApiPost.mockResolvedValue({ message: 'Verification email sent' });
  });

  it('renders Google sign-in button and email continue flow', () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    const googleBtn = screen.getByRole('button', { name: /continue with google/i });
    expect(googleBtn).toBeInTheDocument();
    expect(screen.getByText(/or continue with email/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/email address/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /^continue$/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /forgot password\?/i })).toBeInTheDocument();
  });

  it('successfully signs in with Google, stores token and redirects', async () => {
    const mockUser = {
      email: 'google_user@test.com',
      getIdToken: vi.fn().mockResolvedValue('mock_firebase_id_token_123'),
    };
    mockSignInWithPopup.mockResolvedValueOnce({ user: mockUser });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    const googleBtn = screen.getByRole('button', { name: /continue with google/i });
    fireEvent.click(googleBtn);

    await waitFor(() => {
      expect(mockSignInWithPopup).toHaveBeenCalled();
      expect(localStorage.getItem('token')).toBe('mock_firebase_id_token_123');
      expect(localStorage.getItem('mediskye_user_email')).toBe('google_user@test.com');
      expect(mockNavigate).toHaveBeenCalledWith('/chat');
    });
  });

  it('displays clear error alert banner when Google signInWithPopup fails (popup-closed-by-user or generic error)', async () => {
    const error = new Error('Popup closed');
    error.code = 'auth/popup-closed-by-user';
    mockSignInWithPopup.mockRejectedValueOnce(error);

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    const googleBtn = screen.getByRole('button', { name: /continue with google/i });
    fireEvent.click(googleBtn);

    await waitFor(() => {
      expect(mockSignInWithPopup).toHaveBeenCalled();
      expect(screen.getByRole('alert')).toHaveTextContent(
        "Google sign-in popup was closed before finishing. Please try again."
      );
      expect(googleBtn).not.toBeDisabled();
    });

    // Generic / fallback failure shows "Authentication failed. Please try again."
    const genericErr = new Error('Unknown OAuth error');
    genericErr.code = 'auth/internal-error';
    mockSignInWithPopup.mockRejectedValueOnce(genericErr);
    fireEvent.click(googleBtn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(/authentication failed\. please try again\./i);
      expect(googleBtn).not.toBeDisabled();
    });
  });

  it('signs in with email and password, stores token and redirects when email is verified', async () => {
    const mockUser = {
      email: 'patient@example.com',
      emailVerified: true,
      getIdToken: vi.fn().mockResolvedValue('mock_email_token_456'),
    };
    mockSignInWithEmailAndPassword.mockResolvedValueOnce({ user: mockUser });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    // Step 1: enter email
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: ' Patient@Example.com ' } });
    fireEvent.click(screen.getByRole('button', { name: /^continue$/i }));

    // Step 2: enter password
    expect(screen.getByPlaceholderText(/password/i)).toBeInTheDocument();
    fireEvent.change(screen.getByPlaceholderText(/password/i), { target: { value: 'Secret123!' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockSignInWithEmailAndPassword).toHaveBeenCalledWith(expect.anything(), 'patient@example.com', 'Secret123!');
      expect(localStorage.getItem('token')).toBe('mock_email_token_456');
      expect(localStorage.getItem('mediskye_user_email')).toBe('patient@example.com');
      expect(mockNavigate).toHaveBeenCalledWith('/chat');
    });
  });

  it('blocks unverified email sign-in, signs out, and provides resend verification button', async () => {
    const mockUnverifiedUser = {
      email: 'unverified@example.com',
      emailVerified: false,
      getIdToken: vi.fn(),
    };
    mockSignInWithEmailAndPassword.mockResolvedValueOnce({ user: mockUnverifiedUser });
    mockSignOut.mockResolvedValueOnce();

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'unverified@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /^continue$/i }));

    fireEvent.change(screen.getByPlaceholderText(/password/i), { target: { value: 'Secret123!' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(mockSignInWithEmailAndPassword).toHaveBeenCalledWith(expect.anything(), 'unverified@example.com', 'Secret123!');
      expect(mockSignOut).toHaveBeenCalled();
      expect(screen.getByText(/please verify your email address before logging in\. check your inbox for the link\./i)).toBeInTheDocument();
      expect(screen.getByRole('button', { name: /resend verification email/i })).toBeInTheDocument();
      expect(localStorage.getItem('token')).toBeNull();
      expect(mockNavigate).not.toHaveBeenCalled();
    });

    // Click Resend Verification Email
    const resendBtn = screen.getByRole('button', { name: /resend verification email/i });
    fireEvent.click(resendBtn);

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith('/auth/send-custom-verification', { email: 'unverified@example.com' });
    });
  });

  it('maps auth/invalid-credential error to user-friendly message', async () => {
    const err = new Error('Invalid credential');
    err.code = 'auth/invalid-credential';
    mockSignInWithEmailAndPassword.mockRejectedValueOnce(err);

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /^continue$/i }));

    fireEvent.change(screen.getByPlaceholderText(/password/i), { target: { value: 'wrongpassword' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email or password/i)).toBeInTheDocument();
    });
  });

  it('maps auth/too-many-requests error cleanly', async () => {
    const err = new Error('Too many requests');
    err.code = 'auth/too-many-requests';
    mockSignInWithEmailAndPassword.mockRejectedValueOnce(err);

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'user@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /^continue$/i }));

    fireEvent.change(screen.getByPlaceholderText(/password/i), { target: { value: 'wrongpassword' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByText("Too many attempts. Please wait a minute before requesting another email.")).toBeInTheDocument();
    });
  });

  it('shows validation prompt when clicking Forgot password? with an empty email input', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    const forgotBtn = screen.getByRole('button', { name: /forgot password\?/i });
    fireEvent.click(forgotBtn);

    expect(screen.getByText(/please enter your email address in the field above first/i)).toBeInTheDocument();
    expect(mockSendPasswordResetEmail).not.toHaveBeenCalled();
  });

  it('calls sendCustomPasswordReset and displays confirmation banner when clicking Forgot password? with a valid email', async () => {
    mockApiPost.mockResolvedValueOnce({ message: 'If an account exists with this email, a reset link has been sent.' });

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: ' user@example.com ' } });

    const forgotBtn = screen.getByRole('button', { name: /forgot password\?/i });
    fireEvent.click(forgotBtn);

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith('/auth/send-custom-password-reset', { email: 'user@example.com' });
      expect(screen.getByText(/if an account exists with user@example\.com, a password reset link has been sent/i)).toBeInTheDocument();
    });
  });

  it('does not reveal whether account exists on auth/user-not-found to prevent user enumeration attacks', async () => {
    const err = new Error('User not found');
    mockApiPost.mockRejectedValueOnce(err);

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'notfound@example.com' } });
    const forgotBtn = screen.getByRole('button', { name: /forgot password\?/i });
    fireEvent.click(forgotBtn);

    await waitFor(() => {
      expect(mockApiPost).toHaveBeenCalledWith('/auth/send-custom-password-reset', { email: 'notfound@example.com' });
      expect(screen.getByText(/if an account exists with notfound@example\.com, a password reset link has been sent/i)).toBeInTheDocument();
      expect(screen.queryByText(/no account found with this email address/i)).not.toBeInTheDocument();
    });
  });

  it('validates email format before continuing or resetting password (rejecting notanemail and test@test)', async () => {
    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    const emailInput = screen.getByPlaceholderText(/email address/i);
    const continueBtn = screen.getByRole('button', { name: /^continue$/i });
    const forgotBtn = screen.getByRole('button', { name: /forgot password\?/i });

    // Invalid email on continue
    fireEvent.change(emailInput, { target: { value: 'test@test' } });
    fireEvent.click(continueBtn);
    expect(screen.getByText(/please enter a valid email address \(e\.g\., name@example\.com\)\./i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/password/i)).not.toBeInTheDocument();

    // Invalid email on forgot password
    fireEvent.change(emailInput, { target: { value: 'invalid-email' } });
    fireEvent.click(forgotBtn);
    expect(screen.getByText(/please enter a valid email address \(e\.g\., name@example\.com\)\./i)).toBeInTheDocument();
    expect(mockSendPasswordResetEmail).not.toHaveBeenCalled();
  });
});
