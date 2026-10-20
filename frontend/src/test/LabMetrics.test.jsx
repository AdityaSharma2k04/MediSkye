import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import LabMetrics from '../components/LabMetrics';

describe('LabMetrics Clinical Table', () => {
  const sampleMetrics = [
    { test: 'Hemoglobin', value: '14.2', unit: 'g/dL', range: '12–17', status: 'Normal' },
    { test: 'TSH', value: '0.2', unit: 'mIU/L', range: '0.4–4.0', status: 'Low' },
    { test: 'LDL Cholesterol', value: '160', unit: 'mg/dL', range: '0–100', status: 'High' },
  ];

  it('renders clinical table with semantic columns', () => {
    render(<LabMetrics metrics={sampleMetrics} />);
    expect(screen.getByText('Test Name')).toBeInTheDocument();
    expect(screen.getByText('Value')).toBeInTheDocument();
    expect(screen.getByText('Unit')).toBeInTheDocument();
    expect(screen.getByText('Reference Range')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();

    expect(screen.getByText('Hemoglobin')).toBeInTheDocument();
    expect(screen.getByText('TSH')).toBeInTheDocument();
    expect(screen.getByText('LDL Cholesterol')).toBeInTheDocument();
  });

  it('sorts abnormal metrics (High, Low) to the top before Normal metrics', () => {
    const { container } = render(<LabMetrics metrics={sampleMetrics} />);
    const rows = container.querySelectorAll('tbody tr');
    expect(rows.length).toBe(3);

    // First two rows should be the abnormal tests (TSH and LDL Cholesterol)
    const firstRowText = rows[0].textContent;
    const secondRowText = rows[1].textContent;
    const thirdRowText = rows[2].textContent;

    expect(firstRowText).toMatch(/Low|High/);
    expect(secondRowText).toMatch(/Low|High/);
    expect(thirdRowText).toContain('Hemoglobin');
    expect(thirdRowText).toContain('Normal');
  });

  it('renders status as plain text without background pill badges', () => {
    const { container } = render(<LabMetrics metrics={sampleMetrics} />);
    const statusSpans = container.querySelectorAll('tbody tr td:last-child span');

    expect(statusSpans.length).toBe(3);
    statusSpans.forEach((span) => {
      // Must not have pill background classes or borders
      expect(span.className).not.toContain('rounded-full');
      expect(span.className).not.toContain('bg-red');
      expect(span.className).not.toContain('bg-emerald');
      expect(span.style.fontWeight).toBe('600');
    });
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
});
