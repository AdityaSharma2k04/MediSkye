import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import LabMetrics from '../components/LabMetrics';

describe('LabMetrics Clinical Table', () => {
  const sampleMetrics = [
    { test: 'Hemoglobin', value: '14.2', unit: 'g/dL', range: '12–17', status: 'Normal' },
    { test: 'TSH', value: '0.2', unit: 'mIU/L', range: '0.4–4.0', status: 'Low' },
    { test: 'LDL Cholesterol', value: '160', unit: 'mg/dL', range: '0–100', status: 'High' },
  ];

  const longitudinalMetrics = [
    {
      test: 'Hemoglobin',
      value: '13.6',
      unit: 'g/dL',
      range: '13.0–17.0',
      status: 'Normal',
      previous_value: '15.4',
      previous_date: '24 Oct 2026',
      delta_abs: '-1.8 g/dL',
      delta_pct: -11.7,
      delta_alert: 'Notable Drop (-11.7%)',
    },
    {
      test: 'Vitamin D',
      value: '24.2',
      unit: 'ng/mL',
      range: '30.0–100.0',
      status: 'Low',
      previous_value: '44.2',
      previous_date: '24 Oct 2026',
      delta_abs: '-20.0 ng/mL',
      delta_pct: -45.2,
    },
  ];

  it('renders clinical table with semantic columns', () => {
    render(<LabMetrics metrics={sampleMetrics} />);
    expect(screen.getByText('Test Name')).toBeInTheDocument();
    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('Unit')).toBeInTheDocument();
    expect(screen.getByText('Reference Range')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();

    expect(screen.getAllByText('Hemoglobin')[0]).toBeInTheDocument();
    expect(screen.getAllByText('TSH')[0]).toBeInTheDocument();
    expect(screen.getAllByText('LDL Cholesterol')[0]).toBeInTheDocument();
  });

  it('renders longitudinal columns (Previous (Date) and Change (Δ %)) when prior data is present', () => {
    render(<LabMetrics metrics={longitudinalMetrics} />);
    expect(screen.getByText('Previous (Date)')).toBeInTheDocument();
    expect(screen.getByText('Change (Δ %)')).toBeInTheDocument();
  });

  it('sorts abnormal metrics and delta alerts to the top before Normal metrics', () => {
    const { container } = render(<LabMetrics metrics={sampleMetrics} />);
    const rows = container.querySelectorAll('tbody tr');
    expect(rows.length).toBe(3);

    const firstRowText = rows[0].textContent;
    const secondRowText = rows[1].textContent;
    const thirdRowText = rows[2].textContent;

    expect(firstRowText).toMatch(/Low|High/);
    expect(secondRowText).toMatch(/Low|High/);
    expect(thirdRowText).toContain('Hemoglobin');
    expect(thirdRowText).toContain('Normal');
  });

  it('renders accessible status pills with directional icons', () => {
    const { container } = render(<LabMetrics metrics={longitudinalMetrics} />);
    const pills = container.querySelectorAll('.rounded-full');
    expect(pills.length).toBeGreaterThan(0);

    // Verify directional status pill text
    expect(container.textContent).toContain('↓ Low');
    expect(container.textContent).toContain('Notable Drop');
  });

  it('renders graceful empty state when metrics is empty or null', () => {
    const { rerender } = render(<LabMetrics metrics={[]} />);
    expect(screen.getByText(/No lab metrics available for this report/i)).toBeInTheDocument();

    rerender(<LabMetrics metrics={null} />);
    expect(screen.getByText(/No lab metrics available for this report/i)).toBeInTheDocument();
  });

  it('does not render an Export CSV button', () => {
    render(<LabMetrics metrics={sampleMetrics} />);
    expect(screen.queryByRole('button', { name: /Export CSV/i })).not.toBeInTheDocument();
  });

  it('renders neutral badge for Unknown status on demographic ranges, not Normal green badge', () => {
    const demographicMetrics = [
      { test: 'Hemoglobin', value: '8.2', unit: 'g/dL', range: 'Male: 13.5-17.5; Female: 12.0-15.5', status: 'Unknown' },
    ];
    const { container } = render(<LabMetrics metrics={demographicMetrics} />);
    expect(screen.getAllByText('Hemoglobin')[0]).toBeInTheDocument();
    expect(screen.getAllByText('Unknown')[0]).toBeInTheDocument();
    // Neutral slate badge
    const badge = container.querySelector('.bg-slate-500\\/10');
    expect(badge).toBeInTheDocument();
    // Does NOT render emerald normal badge
    expect(container.querySelector('.bg-emerald-500\\/10')).toBeNull();
  });

  it('renders mobile card list for 390px viewports without horizontal clipping', () => {
    const { container } = render(<LabMetrics metrics={sampleMetrics} />);
    const mobileCardsContainer = container.querySelector('.block.sm\\:hidden');
    expect(mobileCardsContainer).toBeInTheDocument();
  });
});
