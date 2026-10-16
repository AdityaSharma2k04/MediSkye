import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import ChatMessage from '../components/ChatMessage';

describe('ChatMessage rendering', () => {
  it('renders markdown tables correctly', () => {
    const tableMarkdown = '| A | B |\n|---|---|\n| 1 | 2 |';
    const message = {
      sender: 'assistant',
      text: tableMarkdown,
      timestamp: '12:00 PM',
    };

    const { container } = render(<ChatMessage message={message} darkMode={false} />);

    // Assert the rendered output contains <table>
    const table = container.querySelector('table');
    expect(table).toBeInTheDocument();

    const headers = container.querySelectorAll('th');
    expect(headers).toHaveLength(2);
    expect(headers[0].textContent).toBe('A');
    expect(headers[1].textContent).toBe('B');

    const cells = container.querySelectorAll('td');
    expect(cells).toHaveLength(2);
    expect(cells[0].textContent).toBe('1');
    expect(cells[1].textContent).toBe('2');
  });

  it('renders bold text as <strong> element', () => {
    const boldMarkdown = 'This is **bold** text';
    const message = {
      sender: 'assistant',
      text: boldMarkdown,
      timestamp: '12:00 PM',
    };

    const { container } = render(<ChatMessage message={message} darkMode={false} />);

    const strong = container.querySelector('strong');
    expect(strong).toBeInTheDocument();
    expect(strong.textContent).toBe('bold');
  });

  it('renders progressive status line and hides action row while streaming without content', () => {
    const message = {
      sender: 'assistant',
      text: '',
      isStreaming: true,
      status: 'Searching your reports...',
    };

    render(<ChatMessage message={message} darkMode={false} />);

    expect(screen.getByText('Searching your reports...')).toBeInTheDocument();
    // Action bar items (like Copy, Listen) should NOT be rendered while streaming without content
    expect(screen.queryByTitle('Copy response')).not.toBeInTheDocument();
    expect(screen.queryByTitle('Read response aloud')).not.toBeInTheDocument();
  });

  it('renders action row on completion when content is present', () => {
    const message = {
      sender: 'assistant',
      text: 'Here is your personalized summary.',
      isStreaming: false,
    };

    render(<ChatMessage message={message} darkMode={false} />);

    expect(screen.getByText('Here is your personalized summary.')).toBeInTheDocument();
    expect(screen.getByTitle('Copy response')).toBeInTheDocument();
    expect(screen.getByTitle('Read response aloud')).toBeInTheDocument();
  });

  it('renders error state with retry button', () => {
    const handleRegenerate = vi.fn();
    const message = {
      sender: 'assistant',
      text: '',
      error: 'Something went wrong. Tap to retry.',
      isStreaming: false,
    };

    render(<ChatMessage message={message} onRegenerate={handleRegenerate} darkMode={false} />);

    expect(screen.getByText('Something went wrong. Tap to retry.')).toBeInTheDocument();
    const retryBtn = screen.getByRole('button', { name: /retry/i });
    expect(retryBtn).toBeInTheDocument();
    fireEvent.click(retryBtn);
    expect(handleRegenerate).toHaveBeenCalledTimes(1);
  });

  it('renders collapsed metrics expander and reveals table when clicked', () => {
    const message = {
      sender: 'assistant',
      text: 'Analysis complete.',
      metrics: [
        { test: 'Hemoglobin', value: '14.2', unit: 'g/dL', range: '13.5 - 17.5', status: 'Normal' },
        { test: 'Glucose', value: '126', unit: 'mg/dL', range: '70 - 99', status: 'High' },
      ],
      isStreaming: false,
    };

    render(<ChatMessage message={message} darkMode={false} />);

    const expanderBtn = screen.getByText(/View details \(2 tests\)/i);
    expect(expanderBtn).toBeInTheDocument();

    // Table not shown yet
    expect(screen.queryByText('Reference range')).not.toBeInTheDocument();

    // Click to expand
    fireEvent.click(expanderBtn);

    expect(screen.getByText('Hide details')).toBeInTheDocument();
    expect(screen.getByText('Reference range')).toBeInTheDocument();
    expect(screen.getByText('Hemoglobin')).toBeInTheDocument();
    expect(screen.getByText('Glucose')).toBeInTheDocument();
    expect(screen.getByText('High')).toBeInTheDocument();
  });

  it('shows correct count when response has 5 abnormal metrics', () => {
    const message = {
      sender: 'assistant',
      text: 'Analysis complete.',
      metrics: [
        { test: 'HbA1c', value: '7.2', unit: '%', range: '4.0 - 5.6', status: 'High' },
        { test: 'LDL', value: '145', unit: 'mg/dL', range: '0 - 100', status: 'High' },
        { test: 'ALT', value: '62', unit: 'U/L', range: '7 - 40', status: 'High' },
        { test: 'Creatinine', value: '1.4', unit: 'mg/dL', range: '0.7 - 1.2', status: 'High' },
        { test: 'Hemoglobin', value: '10.1', unit: 'g/dL', range: '13.5 - 17.5', status: 'Low' },
      ],
      isStreaming: false,
    };

    render(<ChatMessage message={message} darkMode={false} />);

    expect(screen.getByText(/View details \(5 tests\)/i)).toBeInTheDocument();
  });
});
