import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';
import React from 'react';
import { ReferenceBar, exportMetricsCsv } from '../components/LabMetrics';

describe('ReferenceBar status colors', () => {
  it('renders green dot when value is within range', () => {
    const { container } = render(<ReferenceBar value={5.0} low={4.0} high={6.0} />);
    const dot = container.querySelector('.bg-green-500');
    expect(dot).toBeInTheDocument();
  });

  it('renders red dot when value is above high', () => {
    const { container } = render(<ReferenceBar value={8.0} low={4.0} high={6.0} />);
    const dot = container.querySelector('.bg-red-500');
    expect(dot).toBeInTheDocument();
  });

  it('renders amber dot when value is below low', () => {
    const { container } = render(<ReferenceBar value={2.0} low={4.0} high={6.0} />);
    const dot = container.querySelector('.bg-amber-500');
    expect(dot).toBeInTheDocument();
  });

  it('renders green normal-range band', () => {
    const { container } = render(<ReferenceBar value={5.0} low={4.0} high={6.0} />);
    const band = container.querySelector('.bg-green-300');
    expect(band).toBeInTheDocument();
  });

  it('clamps dot position to 0–100% for extreme values', () => {
    // Should not throw even when value is far outside range
    expect(() => render(<ReferenceBar value={100} low={4.0} high={6.0} />)).not.toThrow();
    expect(() => render(<ReferenceBar value={-100} low={4.0} high={6.0} />)).not.toThrow();
  });
});

describe('exportMetricsCsv', () => {
  let createdUrl;
  let clickedAnchor;

  beforeEach(() => {
    createdUrl = null;
    clickedAnchor = null;

    // JSDOM doesn't implement URL.createObjectURL — define it
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

    // Intercept anchor creation
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
