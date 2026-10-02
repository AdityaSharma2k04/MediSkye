import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import React from 'react';
import HealthProfile from '../components/HealthProfile';
import * as api from '../services/api';

vi.mock('../services/api', () => ({
  getFacts: vi.fn(),
  createFact: vi.fn(),
  updateFact: vi.fn(),
  deleteFact: vi.fn(),
  updateProfile: vi.fn(),
}));

describe('HealthProfile Component', () => {
  const mockUser = {
    id: 'user-123',
    email: 'test@example.com',
    diet_type: 'vegetarian',
    activity_level: 'moderate',
    height_cm: 175,
    occupation: 'Software Engineer',
    memory_consent_granted: true,
  };

  const mockFacts = [
    {
      id: 'f1',
      fact_type: 'condition',
      fact_text: 'Type 2 Diabetes (diagnosed 2019)',
      confidence: 0.95,
      source_type: 'chat',
    },
    {
      id: 'f2',
      fact_type: 'medication',
      fact_text: 'Metformin 500mg twice daily',
      confidence: 0.90,
      source_type: 'pdf',
    },
    {
      id: 'f3',
      fact_type: 'lifestyle',
      fact_text: 'Runs 3 times a week',
      confidence: 0.85,
      source_type: 'chat',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
    api.getFacts.mockResolvedValue([...mockFacts]);
    api.createFact.mockImplementation((fact) =>
      Promise.resolve({
        id: 'f-new',
        ...fact,
        confidence: 1.0,
      })
    );
    api.updateFact.mockImplementation((id, data) =>
      Promise.resolve({
        id,
        fact_text: data.fact_text,
        confidence: 0.95,
      })
    );
    api.deleteFact.mockResolvedValue({ message: 'Deleted' });
    api.updateProfile.mockImplementation((payload) => Promise.resolve({ ...mockUser, ...payload }));
  });

  it('renders facts grouped by type', async () => {
    render(<HealthProfile currentUser={mockUser} darkMode={false} />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /conditions/i })).toBeInTheDocument();
      expect(screen.getByRole('heading', { name: /medications/i })).toBeInTheDocument();
      expect(screen.getByText('Type 2 Diabetes (diagnosed 2019)')).toBeInTheDocument();
      expect(screen.getByText('Metformin 500mg twice daily')).toBeInTheDocument();
      expect(screen.getByText('Runs 3 times a week')).toBeInTheDocument();
    });
  });

  it('edit updates fact via API and updates UI', async () => {
    render(<HealthProfile currentUser={mockUser} darkMode={false} />);

    await waitFor(() => {
      expect(screen.getByText('Type 2 Diabetes (diagnosed 2019)')).toBeInTheDocument();
    });

    const editBtns = screen.getAllByLabelText('Edit fact');
    fireEvent.click(editBtns[0]);

    const editInput = screen.getByLabelText('Edit fact text');
    expect(editInput).toBeInTheDocument();
    fireEvent.change(editInput, { target: { value: 'Type 2 Diabetes well controlled' } });

    const saveBtn = screen.getByLabelText('Save fact edit');
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(api.updateFact).toHaveBeenCalledWith('f1', { fact_text: 'Type 2 Diabetes well controlled' });
      expect(screen.getByText('Type 2 Diabetes well controlled')).toBeInTheDocument();
    });
  });

  it('delete removes fact from list', async () => {
    render(<HealthProfile currentUser={mockUser} darkMode={false} />);

    await waitFor(() => {
      expect(screen.getByText('Type 2 Diabetes (diagnosed 2019)')).toBeInTheDocument();
    });

    const deleteBtns = screen.getAllByLabelText('Forget fact');
    fireEvent.click(deleteBtns[0]);

    await waitFor(() => {
      expect(api.deleteFact).toHaveBeenCalledWith('f1');
      expect(screen.queryByText('Type 2 Diabetes (diagnosed 2019)')).not.toBeInTheDocument();
    });
  });

  it('add appends a new fact to the list', async () => {
    render(<HealthProfile currentUser={mockUser} darkMode={false} />);

    await waitFor(() => {
      expect(screen.getByRole('heading', { name: /conditions/i })).toBeInTheDocument();
    });

    const categorySelect = screen.getByLabelText('Fact Category');
    fireEvent.change(categorySelect, { target: { value: 'allergy' } });

    const input = screen.getByLabelText('Fact Details');
    fireEvent.change(input, { target: { value: 'Penicillin allergy' } });

    const addBtn = screen.getByRole('button', { name: /add fact/i });
    fireEvent.click(addBtn);

    await waitFor(() => {
      expect(api.createFact).toHaveBeenCalledWith(
        expect.objectContaining({
          fact_type: 'allergy',
          fact_text: 'Penicillin allergy',
        })
      );
      expect(screen.getByText('Penicillin allergy')).toBeInTheDocument();
    });
  });

  it('displays empty state message when no facts exist', async () => {
    api.getFacts.mockResolvedValue([]);
    render(<HealthProfile currentUser={mockUser} darkMode={false} />);

    await waitFor(() => {
      expect(screen.getByText('No health facts recorded yet.')).toBeInTheDocument();
    });
  });

  it('lifestyle fields render and edit correctly', async () => {
    const onProfileUpdated = vi.fn();
    render(<HealthProfile currentUser={mockUser} onProfileUpdated={onProfileUpdated} darkMode={false} />);

    // Verify initial values
    const dietSelect = screen.getByLabelText('Diet Pattern');
    expect(dietSelect.value).toBe('vegetarian');

    const activitySelect = screen.getByLabelText('Activity Level');
    expect(activitySelect.value).toBe('moderate');

    const heightInput = screen.getByLabelText('Height (cm)');
    expect(heightInput.value).toBe('175');

    const occupationInput = screen.getByLabelText('Occupation');
    expect(occupationInput.value).toBe('Software Engineer');

    // Change diet pattern
    fireEvent.change(dietSelect, { target: { value: 'vegan' } });
    await waitFor(() => {
      expect(api.updateProfile).toHaveBeenCalledWith({ diet_type: 'vegan' });
    });

    // Change height and blur
    fireEvent.change(heightInput, { target: { value: '180' } });
    fireEvent.blur(heightInput);
    await waitFor(() => {
      expect(api.updateProfile).toHaveBeenCalledWith({ height_cm: 180 });
    });
  });

  it('F5: does not create a duplicate weight fact when the value is unchanged', async () => {
    api.getFacts.mockResolvedValue([
      { id: 'w1', fact_type: 'weight', fact_text: '79 kg', confidence: 1.0, source_type: 'user_edit' },
    ]);
    render(<HealthProfile currentUser={mockUser} darkMode={false} />);

    const weightInput = await screen.findByLabelText('Recent Weight');
    await waitFor(() => expect(weightInput.value).toBe('79 kg'));

    // Blurring repeatedly without editing must NOT spawn new weight facts.
    fireEvent.blur(weightInput);
    fireEvent.blur(weightInput);

    await waitFor(() => {
      expect(api.createFact).not.toHaveBeenCalled();
    });
  });

  it('F5: creates exactly one weight fact when the value changes', async () => {
    api.getFacts.mockResolvedValue([]);
    render(<HealthProfile currentUser={mockUser} darkMode={false} />);

    const weightInput = await screen.findByLabelText('Recent Weight');
    fireEvent.change(weightInput, { target: { value: '80 kg' } });
    fireEvent.blur(weightInput);

    await waitFor(() => expect(api.createFact).toHaveBeenCalledTimes(1));
    expect(api.createFact).toHaveBeenCalledWith(
      expect.objectContaining({ fact_type: 'weight', fact_text: '80 kg' })
    );

    // A second blur with no further edit must not create another fact.
    fireEvent.blur(weightInput);
    await waitFor(() => expect(api.createFact).toHaveBeenCalledTimes(1));
  });
});
