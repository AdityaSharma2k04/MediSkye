import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import UploadStepper from '../components/workbench/UploadStepper';
import RangeBar from '../components/clinical/RangeBar';
import LabMetrics from '../components/LabMetrics';
import OrganSystemsOverview from '../components/clinical/OrganSystemsOverview';
import Sheet from '../components/ui/Sheet';
import ChatWindow, { cleanGreetingName } from '../components/ChatWindow';

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

describe('Sheet centered variant', () => {
  it('renders centered without pointer-events wrapping div and supports escape and close', () => {
    const onOpenChange = vi.fn();
    render(
      <Sheet open={true} onOpenChange={onOpenChange} title="Actions" variant="center" width={420}>
        <div>Sheet body content</div>
      </Sheet>
    );
    const dialog = screen.getByRole('dialog');
    expect(dialog).toBeInTheDocument();
    expect(dialog.className).toContain('fixed');
    expect(dialog.className).toContain('inset-x-0');
    expect(dialog.className).toContain('mx-auto');
    expect(dialog.className).toContain('top-[12dvh]');
    expect(screen.getByText('Sheet body content')).toBeInTheDocument();

    // Close button dismisses
    const closeBtn = screen.getByRole('button', { name: /Close Actions/i });
    fireEvent.click(closeBtn);
    expect(onOpenChange).toHaveBeenCalledWith(false);

    // Escape key dismisses
    fireEvent.keyDown(dialog, { key: 'Escape', code: 'Escape' });
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });
});

describe('ChatWindow Greeting & Fallback Name', () => {
  it('cleanGreetingName filters out invalid/placeholder names', () => {
    expect(cleanGreetingName(null)).toBeNull();
    expect(cleanGreetingName('')).toBeNull();
    expect(cleanGreetingName('   ')).toBeNull();
    expect(cleanGreetingName('my')).toBeNull();
    expect(cleanGreetingName('My profile')).toBeNull();
    expect(cleanGreetingName('user@example.com')).toBeNull();
    expect(cleanGreetingName('patient')).toBeNull();
    expect(cleanGreetingName('null')).toBeNull();
    expect(cleanGreetingName('undefined')).toBeNull();
    expect(cleanGreetingName('Aditya Sharma')).toBe('Aditya');
    expect(cleanGreetingName('Priya')).toBe('Priya');
  });

  it('renders clean greeting without "my" or dangling comma when name is null or loading', () => {
    const { container } = render(
      <ChatWindow
        messages={[]}
        isGenerating={false}
        currentUser={{ full_name: null, email: 'patient@example.com' }}
        patientName={null}
      />
    );

    const greetingEl = container.querySelector('.text-sm.text-ink-mute');
    expect(greetingEl).not.toBeNull();
    const text = greetingEl.textContent;
    // Must match greeting pattern
    expect(text).toMatch(/^(Good morning|Good afternoon|Good evening|Working late)\.$/);
    // Must NOT contain "my", "patient", or dangling comma
    expect(text.toLowerCase()).not.toContain('my');
    expect(text.toLowerCase()).not.toContain('patient');
    expect(text).not.toContain(',');
  });

  it('renders personalized greeting when valid full_name is present', () => {
    const { container } = render(
      <ChatWindow
        messages={[]}
        isGenerating={false}
        currentUser={{ full_name: 'Aditya Sharma' }}
      />
    );

    const greetingEl = container.querySelector('.text-sm.text-ink-mute');
    expect(greetingEl).not.toBeNull();
    const text = greetingEl.textContent;
    expect(text).toMatch(/^(Good morning|Good afternoon|Good evening|Working late), Aditya\.$/);
  });
});
