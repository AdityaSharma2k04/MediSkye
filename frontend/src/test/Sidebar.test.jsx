import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
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
  getGeneralChats: vi.fn().mockResolvedValue([]),
  renameChatSession: vi.fn(),
  deleteChatSession: vi.fn().mockResolvedValue(true),
  clearAllChatSessions: vi.fn().mockResolvedValue(true),
  updateProfile: vi.fn(),
  deleteAccount: vi.fn(),
  logout: vi.fn(),
  sendQueryStream: vi.fn(),
  detachChatDocument: vi.fn(),
  fetchLabMetrics: vi.fn().mockResolvedValue([]),
  getMemoryStatus: vi.fn().mockResolvedValue({ memory_consent_granted: true }),
  getMemoryFacts: vi.fn().mockResolvedValue([]),
  getFacts: vi.fn().mockResolvedValue([]),
  reassignDocumentPatient: vi.fn().mockResolvedValue({ status: 'ok' }),
  getCachedProfile: vi.fn().mockReturnValue(null),
  getCachedDependents: vi.fn().mockReturnValue([]),
  getCachedDocuments: vi.fn().mockReturnValue([]),
  setCachedDocuments: vi.fn(),
  setCachedProfile: vi.fn(),
  setCachedDependents: vi.fn(),
}));

describe('Sidebar DeepSeek-style Slide Collapse Animation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    // Tablet/mobile viewport so header Toggle sidebar control is rendered
    window.innerWidth = 800;
  });

  afterEach(() => {
    window.innerWidth = 1024;
  });

  it('clicking toggle changes class from translate-x-0 to -translate-x-full and updates localStorage', async () => {
    localStorage.setItem('mediskye_sidebar_open', 'true');

    const { container } = render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    const toggleButton = await screen.findByRole('button', { name: /toggle sidebar/i });
    const sidebarWrapper = container.querySelector('[data-testid="sidebar-wrapper"]');
    expect(sidebarWrapper).toBeInTheDocument();
    // At tablet/mobile width (< 1024px), the drawer starts closed; open it first
    if (sidebarWrapper.className.includes('-translate-x-full')) {
      fireEvent.click(toggleButton);
    }
    expect(sidebarWrapper.className).toContain('translate-x-0');
    expect(sidebarWrapper.className).not.toContain('-translate-x-full');

    // Click toggle to collapse sidebar
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(sidebarWrapper.className).toContain('-translate-x-full');
      expect(sidebarWrapper.className).not.toContain('translate-x-0');
      expect(localStorage.getItem('mediskye_sidebar_open')).toBe('false');
    });

    // Click toggle again to expand sidebar
    fireEvent.click(toggleButton);

    await waitFor(() => {
      expect(sidebarWrapper.className).toContain('translate-x-0');
      expect(sidebarWrapper.className).not.toContain('-translate-x-full');
      expect(localStorage.getItem('mediskye_sidebar_open')).toBe('true');
    });
  });

  it('defaults closed on mobile screens (< 768px)', async () => {
    window.innerWidth = 500;
    localStorage.removeItem('mediskye_sidebar_open');

    const { container } = render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    await waitFor(() => {
      const sidebarWrapper = container.querySelector('[data-testid="sidebar-wrapper"]');
      expect(sidebarWrapper).toBeInTheDocument();
      expect(sidebarWrapper.className).toContain('-translate-x-full');
    });
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

  it('does not display Rename or Delete menu on initial render for new accounts', async () => {
    window.innerWidth = 1024;
    localStorage.clear();
    localStorage.setItem('mediskye_sidebar_open', 'true');
    localStorage.setItem('token', 'jwt-new-user');

    render(
      <MemoryRouter>
        <ChatApp />
      </MemoryRouter>
    );

    // Initial conversation is visible (both top button and chat item have this text)
    const elements = await screen.findAllByText('New Conversation');
    expect(elements.length).toBeGreaterThan(0);

    // Dropdown items (Rename / Delete) must NOT be visible initially
    expect(screen.queryByRole('button', { name: /^rename$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /^delete$/i })).not.toBeInTheDocument();
  });
});

