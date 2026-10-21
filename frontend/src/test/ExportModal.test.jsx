import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import React from 'react';
import ExportModal from '../components/ExportModal';

vi.mock('../services/api', () => ({
  exportDocumentData: vi.fn(),
}));

import * as api from '../services/api';

const EXPORT_PAYLOAD = {
  document: {
    id: 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee',
    filename: 'blood_test.pdf',
    title: 'Blood Test',
    created_at: '2026-01-05T10:00:00Z',
  },
  messages: [
    { id: 'm1', role: 'user', message: 'Is my hemoglobin normal?', created_at: '2026-01-05T10:01:00Z' },
    { id: 'm2', role: 'ai', message: 'Yes, your hemoglobin is within the normal range.', created_at: '2026-01-05T10:01:05Z' },
  ],
  lab_metrics: [
    { test: 'Hemoglobin', value: '14.2', unit: 'g/dL', range: '12-17', status: 'Normal' },
  ],
};

describe('ExportModal', () => {
  let createObjectURLSpy;
  let revokeObjectURLSpy;
  let printSpy;

  beforeEach(() => {
    vi.clearAllMocks();
    createObjectURLSpy = vi.fn(() => 'blob:mediskye-test');
    revokeObjectURLSpy = vi.fn();
    printSpy = vi.fn();
    URL.createObjectURL = createObjectURLSpy;
    URL.revokeObjectURL = revokeObjectURLSpy;
    window.print = printSpy;
    api.exportDocumentData.mockResolvedValue(EXPORT_PAYLOAD);
  });

  it('downloads a JSON file with the full transcript and metrics', async () => {
    const showToast = vi.fn();
    render(
      <ExportModal
        isOpen
        onClose={() => {}}
        darkMode
        documentId="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        documentTitle="Blood Test"
        messages={[]}
        user={{ full_name: 'Test User' }}
        showToast={showToast}
      />
    );

    fireEvent.click(screen.getByText('Download JSON'));

    await waitFor(() => expect(api.exportDocumentData).toHaveBeenCalledWith('aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'));
    await waitFor(() => expect(createObjectURLSpy).toHaveBeenCalled());

    // The blob must contain the exported transcript + metrics
    const blob = createObjectURLSpy.mock.calls[0][0];
    expect(blob.type).toBe('application/json');
    const text = await blob.text();
    const parsed = JSON.parse(text);
    expect(parsed.messages).toHaveLength(2);
    expect(parsed.messages[0].message).toBe('Is my hemoglobin normal?');
    expect(parsed.lab_metrics[0].test).toBe('Hemoglobin');

    expect(showToast).toHaveBeenCalledWith('success', 'Export Downloaded', expect.any(String));
  });

  it('falls back to in-memory messages for general chats without a document', async () => {
    render(
      <ExportModal
        isOpen
        onClose={() => {}}
        darkMode={false}
        documentId={null}
        documentTitle={null}
        messages={[
          { id: 'g1', sender: 'user', text: 'What causes high blood pressure?' },
          { id: 'g2', sender: 'assistant', text: 'Several factors contribute...' },
        ]}
        showToast={() => {}}
      />
    );

    fireEvent.click(screen.getByText('Download JSON'));

    await waitFor(() => expect(createObjectURLSpy).toHaveBeenCalled());
    const blob = createObjectURLSpy.mock.calls[0][0];
    const parsed = JSON.parse(await blob.text());
    expect(parsed.messages).toHaveLength(2);
    expect(parsed.messages[0].role).toBe('user');
    expect(parsed.messages[1].role).toBe('ai');
  });

  it('renders the printable transcript and triggers window.print for PDF', async () => {
    const { container } = render(
      <ExportModal
        isOpen
        onClose={() => {}}
        darkMode
        documentId="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
        documentTitle="Blood Test"
        messages={[]}
        user={{ full_name: 'Test User' }}
        showToast={() => {}}
      />
    );

    await act(async () => {
      fireEvent.click(screen.getByText('Download PDF'));
    });
    await waitFor(() => expect(printSpy).toHaveBeenCalledTimes(1), { timeout: 5000 });
    // Transcript must be mounted while printing, containing disclaimer + metrics
    const transcript = container.querySelector('#print-transcript');
    expect(transcript).not.toBeNull();
    expect(transcript.textContent).toContain('Consultation Transcript');
    expect(transcript.textContent).toContain('Hemoglobin');
    expect(transcript.textContent).toContain('not a substitute for professional medical advice');

    // When the browser fires afterprint, the print document is unmounted
    await act(async () => {
      window.dispatchEvent(new Event('afterprint'));
    });
    await waitFor(() => expect(container.querySelector('#print-transcript')).toBeNull());
  });

  it('renders nothing when closed', () => {
    const { container } = render(
      <ExportModal isOpen={false} onClose={() => {}} darkMode />
    );
    expect(container.querySelector('[role="dialog"]')).toBeNull();
  });
});
