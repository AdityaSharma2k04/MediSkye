import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import ChatApp from '../components/ChatApp';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getProfile: vi.fn().mockResolvedValue({
    id: 'test-user-id',
    email: 'test@example.com',
    full_name: 'Test Patient',
    memory_consent_granted: true,
  }),
  getDependents: vi.fn().mockResolvedValue([]),
  getUserDocuments: vi.fn().mockResolvedValue([]),
  getDocumentChats: vi.fn().mockResolvedValue([]),
  updateProfile: vi.fn(),
  deleteAccount: vi.fn(),
  logout: vi.fn(),
  sendQueryStream: vi.fn(),
  detachChatDocument: vi.fn(),
  fetchLabMetrics: vi.fn().mockResolvedValue([]),
  getMemoryStatus: vi.fn().mockResolvedValue({ memory_consent_granted: true }),
  getMemoryFacts: vi.fn().mockResolvedValue([]),
  getFacts: vi.fn().mockResolvedValue([]),
}));

describe('Sidebar DeepSeek-style Slide Collapse Animation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Default to desktop viewport
    window.innerWidth = 1024;
  });

  it('clicking toggle changes class from translate-x-0 to -translate-x-full and updates localStorage', async () => {
    localStorage.setItem('mediskye_sidebar_open', 'true');

    const { container } = render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    const sidebarWrapper = container.querySelector('[data-testid="sidebar-wrapper"]');
    expect(sidebarWrapper).toBeInTheDocument();
    expect(sidebarWrapper.className).toContain('translate-x-0');
    expect(sidebarWrapper.className).not.toContain('-translate-x-full');

    // Find the toggle button in the chat header
    const toggleButton = screen.getByRole('button', { name: /toggle sidebar/i });
    expect(toggleButton).toBeInTheDocument();

    // Click toggle to collapse sidebar
    fireEvent.click(toggleButton);

    expect(sidebarWrapper.className).toContain('-translate-x-full');
    expect(sidebarWrapper.className).not.toContain('translate-x-0');
    expect(localStorage.getItem('mediskye_sidebar_open')).toBe('false');

    // Click toggle again to expand sidebar
    fireEvent.click(toggleButton);

    expect(sidebarWrapper.className).toContain('translate-x-0');
    expect(sidebarWrapper.className).not.toContain('-translate-x-full');
    expect(localStorage.getItem('mediskye_sidebar_open')).toBe('true');
  });

  it('defaults closed on mobile screens (< 768px)', async () => {
    window.innerWidth = 500;
    localStorage.removeItem('mediskye_sidebar_open');

    const { container } = render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    const sidebarWrapper = container.querySelector('[data-testid="sidebar-wrapper"]');
    expect(sidebarWrapper.className).toContain('-translate-x-full');
  });

  it('exposes a Log out control that clears auth after confirmation', async () => {
    window.innerWidth = 1024;
    localStorage.setItem('mediskye_sidebar_open', 'true');
    localStorage.setItem('token', 'jwt-abc');

    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // Sidebar is open, so its footer Log out button is reachable.
    const logoutBtn = await screen.findByRole('button', { name: /log out/i });
    fireEvent.click(logoutBtn);

    // Confirmation dialog appears before anything is cleared.
    const dialog = await screen.findByRole('dialog');
    expect(within(dialog).getByText('Log out of MediSkye?')).toBeInTheDocument();
    expect(api.logout).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole('button', { name: 'Log out' }));

    await waitFor(() => expect(api.logout).toHaveBeenCalledTimes(1));
  });
});
