import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import UploadStepper from '../components/workbench/UploadStepper';
import RangeBar from '../components/clinical/RangeBar';
import LabMetrics from '../components/LabMetrics';
import OrganSystemsOverview from '../components/clinical/OrganSystemsOverview';

const metrics = [
  { test: 'Hemoglobin', value: '11.6', unit: 'g/dL', range: '12.0–15.5', status: 'Low', previous_value: '13.1', delta_pct: -11.5, delta_alert: 'Notable Drop (-11.5%)' },
  { test: 'Ferritin', value: '238', unit: 'pg/mL', range: '200–900', status: 'Normal' },
  { test: 'LDL Cholesterol', value: '162', unit: 'mg/dL', range: '<100', status: 'High' },
];

describe('UploadStepper', () => {
  it('renders the four pipeline stages and marks earlier stages complete', () => {
    render(<UploadStepper upload={{ phase: 'indexing', fileName: 'cbc.pdf', startedAt: Date.now() }} />);
    const banner = screen.getByTestId('upload-progress-banner');
    expect(banner).toHaveTextContent('Processing report...');
    expect(banner).toHaveTextContent('Validating PDF');
    expect(banner).toHaveTextContent('Extracting clinical text');
    expect(banner).toHaveTextContent('Building hybrid FAISS + BM25 index');
    expect(banner).toHaveTextContent('Ready for Q&A');
  });

  it('shows the background cache-warming badge once ready', () => {
    render(<UploadStepper upload={{ phase: 'ready', fileName: 'cbc.pdf', startedAt: Date.now() - 1000, finishedAt: Date.now(), warming: true }} onDismiss={vi.fn()} />);
    expect(screen.getByText('Warming summary cache')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Dismiss upload status' })).toBeInTheDocument();
  });
});

describe('RangeBar', () => {
  it('exposes a sentence-style accessible label (img, not progressbar)', () => {
    render(<RangeBar row={metrics[1]} />);
    const img = screen.getByRole('img');
    expect(img.getAttribute('aria-label')).toMatch(/Ferritin 238 pg\/mL/);
    expect(img.getAttribute('aria-label')).toMatch(/Near the bottom of 200–900/);
    expect(document.querySelector('[role="progressbar"]')).toBeNull();
  });
});

describe('LabMetrics quick filters', () => {
  it('filters to flagged and notable-drop rows', () => {
    const { container } = render(<LabMetrics metrics={metrics} />);
    expect(container.querySelectorAll('tbody tr')).toHaveLength(3);

    fireEvent.click(screen.getByRole('button', { name: /Flagged only/i }));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(2);

    fireEvent.click(screen.getByRole('button', { name: /Notable drops/i }));
    expect(container.querySelectorAll('tbody tr')).toHaveLength(1);
    expect(container.querySelector('tbody').textContent).toContain('Hemoglobin');
  });

  it('calls onAskAbout with the biomarker row', () => {
    const onAskAbout = vi.fn();
    render(<LabMetrics metrics={metrics} onAskAbout={onAskAbout} layout="list" />);
    fireEvent.click(screen.getByRole('button', { name: 'Ask MediSkye about Ferritin' }));
    expect(onAskAbout).toHaveBeenCalledWith(metrics[1]);
  });
});

describe('OrganSystemsOverview', () => {
  it('headlines how many values need attention and lets you apply a filter', () => {
    const onApplyFilter = vi.fn();
    render(<OrganSystemsOverview metrics={metrics} onApplyFilter={onApplyFilter} />);
    expect(screen.getByText('2 of 3 values need attention')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Notable drops/i }));
    expect(onApplyFilter).toHaveBeenCalledWith('drops');
  });
});
