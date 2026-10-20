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

vi.mock('../services/firebase', async () => {
  const actual = await vi.importActual('../services/firebase');
  return {
    ...actual,
    auth: {},
    googleProvider: {},
    signInWithPopup: (...args) => mockSignInWithPopup(...args),
    signInWithEmailAndPassword: (...args) => mockSignInWithEmailAndPassword(...args),
    sendPasswordResetEmail: (...args) => mockSendPasswordResetEmail(...args),
  };
});

describe('Login Component with Firebase Auth & Password Reset', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
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

  it('handles popup-closed-by-user gracefully without error banner', async () => {
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
    });
    expect(screen.queryByText(/google sign-in failed/i)).not.toBeInTheDocument();
  });

  it('signs in with email and password, stores token and redirects', async () => {
    const mockUser = {
      email: 'patient@example.com',
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
      expect(screen.getByText(/too many reset attempts|too many failed attempts/i)).toBeInTheDocument();
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

  it('calls sendPasswordResetEmail and displays confirmation banner when clicking Forgot password? with a valid email', async () => {
    mockSendPasswordResetEmail.mockResolvedValueOnce();

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: ' user@example.com ' } });

    const forgotBtn = screen.getByRole('button', { name: /forgot password\?/i });
    fireEvent.click(forgotBtn);

    await waitFor(() => {
      expect(mockSendPasswordResetEmail).toHaveBeenCalledWith(expect.anything(), 'user@example.com');
      expect(screen.getByText(/password reset link sent to user@example\.com/i)).toBeInTheDocument();
    });
  });

  it('maps auth/user-not-found error on password reset attempt', async () => {
    const err = new Error('User not found');
    err.code = 'auth/user-not-found';
    mockSendPasswordResetEmail.mockRejectedValueOnce(err);

    render(
      <MemoryRouter>
        <Login />
      </MemoryRouter>
    );

    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: 'notfound@example.com' } });
    const forgotBtn = screen.getByRole('button', { name: /forgot password\?/i });
    fireEvent.click(forgotBtn);

    await waitFor(() => {
      expect(screen.getByText(/no account found with this email address/i)).toBeInTheDocument();
    });
  });
});
