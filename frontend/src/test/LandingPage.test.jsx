import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LandingPage from '../components/LandingPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

describe('LandingPage Component', () => {
  beforeEach(() => {
    localStorage.clear();
    mockNavigate.mockClear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('renders primary hero headline and call-to-action buttons', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1 })).toHaveTextContent(/Understand your medical reports/i);
    expect(screen.getByRole('link', { name: /start for free/i })).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: /sign in/i }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByRole('link', { name: /get started/i }).length).toBeGreaterThanOrEqual(1);
  });

  it('renders safety section with clinical boundaries', () => {
    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { name: /^MediSkye can$/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /^MediSkye cannot$/i })).toBeInTheDocument();
  });

  it('redirects to /chat if valid token is found in localStorage', () => {
    const validExp = Math.floor(Date.now() / 1000) + 3600;
    const dummyToken = `header.${btoa(JSON.stringify({ exp: validExp }))}.sig`;
    localStorage.setItem('token', dummyToken);

    render(
      <MemoryRouter>
        <LandingPage />
      </MemoryRouter>
    );

    expect(mockNavigate).toHaveBeenCalledWith('/chat', { replace: true });
  });
});
