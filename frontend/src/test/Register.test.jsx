import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import Register from '../components/Register';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  register: vi.fn(),
}));

describe('Register Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

  it('validates email format before advancing to password step', () => {
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

    expect(screen.getByText(/please enter a valid email address/i)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/create a password/i)).not.toBeInTheDocument();
  });

  it('advances to password step and displays 8 character password requirement', () => {
    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    const emailInput = screen.getByPlaceholderText(/email address/i);
    const continueBtn = screen.getByRole('button', { name: /continue/i });

    fireEvent.change(emailInput, { target: { value: 'user@example.com' } });
    fireEvent.click(continueBtn);

    expect(screen.getByPlaceholderText(/create a password/i)).toBeInTheDocument();
    expect(screen.getByText(/must be 8 to 72 characters/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
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
    
    // Check consent
    const consentInput = document.getElementById('register-phi-consent');
    fireEvent.click(consentInput);

    // Submit
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(screen.getByText(/password must be at least 8 characters/i)).toBeInTheDocument();
    expect(api.register).not.toHaveBeenCalled();
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
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(screen.getByText(/you must consent to phi processing/i)).toBeInTheDocument();
    expect(api.register).not.toHaveBeenCalled();
  });

  it('calls register API with trimmed email, password, and consent', async () => {
    api.register.mockResolvedValueOnce({ id: '123', email: 'user@example.com' });

    render(
      <MemoryRouter>
        <Register />
      </MemoryRouter>
    );

    // Step 1: enter email with whitespace
    fireEvent.change(screen.getByPlaceholderText(/email address/i), { target: { value: '  user@example.com  ' } });
    fireEvent.click(screen.getByRole('button', { name: /continue/i }));

    // Step 2: enter valid password and check consent
    fireEvent.change(screen.getByPlaceholderText(/create a password/i), { target: { value: 'validPassword123' } });
    const consentInput = document.getElementById('register-phi-consent');
    fireEvent.click(consentInput);

    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(api.register).toHaveBeenCalledWith('user@example.com', 'validPassword123', true);
    });

    expect(screen.getByText(/account created! redirecting/i)).toBeInTheDocument();
  });

  it('displays API error message clearly', async () => {
    api.register.mockRejectedValueOnce(new Error('The user with this email already exists in the system.'));

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
    fireEvent.click(document.getElementById('register-phi-consent'));
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByText(/the user with this email already exists in the system/i)).toBeInTheDocument();
    });
  });
});
