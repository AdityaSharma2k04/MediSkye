import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import MemoryVault from '../components/workbench/MemoryVault';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getFacts: vi.fn(),
  getMemoryFacts: vi.fn(),
  deleteFact: vi.fn(),
  clearAllMemoryFacts: vi.fn(),
  updateMemoryConsent: vi.fn(),
  updateProfile: vi.fn(),
  getDependents: vi.fn(),
  getCachedMemoryFacts: vi.fn().mockReturnValue([]),
  setCachedMemoryFacts: vi.fn(),
}));

describe('MemoryVault Independent Patient Selector', () => {
  const mockUser = {
    id: 'user-primary-123',
    full_name: 'Dr. Jane Doe',
    email: 'jane@example.com',
    memory_consent_granted: true,
  };

  const mockDependents = [
    { id: 'dep-uuid-1', full_name: 'Timmy Doe', relationship: 'son' },
    { id: 'dep-uuid-2', full_name: 'Grandpa Bob', relationship: 'father' },
  ];

  const selfFacts = [
    { id: 'fact-1', fact_text: 'Hypertension diagnosed in 2020', fact_type: 'condition', created_at: '2026-01-10T10:00:00Z' },
  ];

  const timmyFacts = [
    { id: 'fact-2', fact_text: 'Peanut allergy with severe reaction', fact_type: 'allergy', created_at: '2026-02-15T10:00:00Z' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    api.getFacts.mockImplementation((patientId) => {
      if (patientId === 'dep-uuid-1') {
        return Promise.resolve(timmyFacts);
      }
      return Promise.resolve(selfFacts);
    });
    api.deleteFact.mockResolvedValue({ message: 'Fact deleted successfully' });
    api.clearAllMemoryFacts.mockResolvedValue({ message: 'All facts cleared' });
    api.getDependents.mockResolvedValue(mockDependents);
  });

  it('renders dropdown with Self and all dependents', async () => {
    render(
      <MemoryVault
        open={true}
        onOpenChange={vi.fn()}
        selectedPatientId="self"
        currentUser={mockUser}
        dependents={mockDependents}
      />
    );

    const select = await screen.findByTestId('memory-vault-patient-select');
    expect(select).toBeInTheDocument();
    expect(select.value).toBe('self');

    // Check options
    const options = screen.getAllByRole('option');
    expect(options).toHaveLength(3);
    expect(options[0]).toHaveTextContent('Dr. Jane Doe (Self)');
    expect(options[1]).toHaveTextContent('Timmy Doe (son)');
    expect(options[2]).toHaveTextContent('Grandpa Bob (father)');

    // Initial fetch should be called with 'self'
    await waitFor(() => {
      expect(api.getFacts).toHaveBeenCalledWith('self');
      expect(screen.getByText('Hypertension diagnosed in 2020')).toBeInTheDocument();
    });
  });

  it('switching dropdown fetches facts for that dependent without changing parent state', async () => {
    render(
      <MemoryVault
        open={true}
        onOpenChange={vi.fn()}
        selectedPatientId="self"
        currentUser={mockUser}
        dependents={mockDependents}
      />
    );

    const select = await screen.findByTestId('memory-vault-patient-select');
    expect(select.value).toBe('self');

    // Switch to Timmy
    fireEvent.change(select, { target: { value: 'dep-uuid-1' } });
    expect(select.value).toBe('dep-uuid-1');

    await waitFor(() => {
      expect(api.getFacts).toHaveBeenCalledWith('dep-uuid-1');
      expect(screen.getByText('Peanut allergy with severe reaction')).toBeInTheDocument();
    });

    // Deleting a fact for Timmy passes Timmy's dependent ID
    const deleteBtn = screen.getByRole('button', { name: /Forget:/i });
    fireEvent.click(deleteBtn);

    await waitFor(() => {
      expect(api.deleteFact).toHaveBeenCalledWith('fact-2', 'dep-uuid-1');
    });
  });

  it('fetches dependents on mount if dependents prop is empty', async () => {
    render(
      <MemoryVault
        open={true}
        onOpenChange={vi.fn()}
        selectedPatientId="self"
        currentUser={mockUser}
        dependents={[]}
      />
    );

    await waitFor(() => {
      expect(api.getDependents).toHaveBeenCalled();
    });

    const select = await screen.findByTestId('memory-vault-patient-select');
    const options = await screen.findAllByRole('option');
    expect(options.length).toBeGreaterThanOrEqual(2);
  });
});
