import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import LabMetrics, { exportMetricsCsv } from '../components/LabMetrics';

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
});

describe('exportMetricsCsv', () => {
  let createdUrl;
  let clickedAnchor;

  beforeEach(() => {
    createdUrl = null;
    clickedAnchor = null;

    if (!URL.createObjectURL) {
      URL.createObjectURL = () => 'blob:mock-url';
    }
    if (!URL.revokeObjectURL) {
      URL.revokeObjectURL = () => {};
    }

    vi.spyOn(URL, 'createObjectURL').mockImplementation((blob) => {
      createdUrl = blob;
      return 'blob:mock-url';
    });
    vi.spyOn(URL, 'revokeObjectURL').mockImplementation(() => {});

    const origCreate = document.createElement.bind(document);
    vi.spyOn(document, 'createElement').mockImplementation((tag) => {
      const el = origCreate(tag);
      if (tag === 'a') {
        clickedAnchor = el;
        vi.spyOn(el, 'click').mockImplementation(() => {});
      }
      return el;
    });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('creates a Blob with CSV content-type', () => {
    const metrics = [
      { test: 'Glucose', value: '110', unit: 'mg/dL', range: '70–99', status: 'High' },
      { test: 'Hemoglobin', value: '14.2', unit: 'g/dL', range: '12–17', status: 'Normal' },
    ];
    exportMetricsCsv(metrics);
    expect(createdUrl).toBeInstanceOf(Blob);
    expect(createdUrl.type).toBe('text/csv;charset=utf-8;');
  });

  it('sets download filename to lab_metrics.csv', () => {
    exportMetricsCsv([{ test: 'TSH', value: '2.5', unit: 'mIU/L', range: '0.4–4.0', status: 'Normal' }]);
    expect(clickedAnchor.download).toBe('lab_metrics.csv');
  });

  it('includes header row and all metric fields', async () => {
    const metrics = [
      { test: 'LDL', value: '160', unit: 'mg/dL', range: '0–100', status: 'High' },
    ];
    exportMetricsCsv(metrics);
    const text = await createdUrl.text();
    expect(text).toContain('Test');
    expect(text).toContain('LDL');
    expect(text).toContain('High');
    expect(text).toContain('Lipid'); // category
  });

  it('revokes the object URL after click', () => {
    exportMetricsCsv([{ test: 'ALT', value: '45', unit: 'U/L', range: '7–56', status: 'Normal' }]);
    expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:mock-url');
  });
});
