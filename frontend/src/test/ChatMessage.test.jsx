import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import React from 'react';
import ChatMessage, { stripAbnormalFlags, cleanMessageText } from '../components/ChatMessage';

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

  it('does not render View details or metadata table when message has metrics', () => {
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

    expect(screen.queryByText(/View details/i)).not.toBeInTheDocument();
    expect(screen.queryByText('Reference range')).not.toBeInTheDocument();
    expect(screen.getByText('Analysis complete.')).toBeInTheDocument();
  });

  it('renders only plain response text and no test counts for multiple metrics', () => {
    const message = {
      sender: 'assistant',
      text: 'Your blood panel summary.',
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

    expect(screen.queryByText(/View details/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/tests/i)).not.toBeInTheDocument();
    expect(screen.getByText('Your blood panel summary.')).toBeInTheDocument();
  });

  describe('abnormal_flags stripping', () => {
    it('strips completed abnormal_flags JSON block from string', () => {
      const raw = 'Here is your report.\n\n```json\n{\n  "abnormal_flags": [\n    "WBC (Total Leucocyte Count)"\n  ]\n}\n```';
      const cleaned = stripAbnormalFlags(raw);
      expect(cleaned).toBe('Here is your report.');
      expect(cleaned).not.toContain('abnormal_flags');
      expect(cleaned).not.toContain('```json');
    });

    it('strips unclosed abnormal_flags JSON block during streaming', () => {
      const raw = 'Here is your report.\n\n```json\n{\n  "abnormal_flags": [\n    "WBC"';
      const cleaned = stripAbnormalFlags(raw);
      expect(cleaned).toBe('Here is your report.');
      expect(cleaned).not.toContain('abnormal_flags');
      expect(cleaned).not.toContain('```json');
    });

    it('renders assistant message without abnormal_flags JSON block leaking into DOM', () => {
      const message = {
        sender: 'assistant',
        text: 'Total WBC count is slightly elevated.\n\n```json\n{\n  "abnormal_flags": ["WBC"]\n}\n```',
        isStreaming: false,
      };

      const { container } = render(<ChatMessage message={message} darkMode={false} />);

      expect(screen.getByText(/Total WBC count is slightly elevated/)).toBeInTheDocument();
      expect(container.textContent).not.toContain('abnormal_flags');
      expect(container.textContent).not.toContain('```json');
    });

    it('renders streaming assistant message without unclosed abnormal_flags JSON block', () => {
      const message = {
        sender: 'assistant',
        text: 'Your eosinophil count is high.\n\n```json\n{\n  "abnormal_flags": ["AEC"',
        isStreaming: true,
      };

      const { container } = render(<ChatMessage message={message} darkMode={false} />);

      expect(screen.getByText(/Your eosinophil count is high/)).toBeInTheDocument();
      expect(container.textContent).not.toContain('abnormal_flags');
      expect(container.textContent).not.toContain('```json');
    });

    it('deduplicates multiple disclaimers on first overview (isFollowupTurn=false)', () => {
      const message = {
        sender: 'assistant',
        text: '### 🟢 The Short Version\nNormal results.\n\n**Disclaimer:** First disclaimer.\n\n***\n\n**Disclaimer:** Second disclaimer.',
      };

      const { container } = render(<ChatMessage message={message} isFollowupTurn={false} />);
      const text = container.textContent;
      const count = (text.match(/Disclaimer:/g) || []).length;
      expect(count).toBe(1);
      expect(text).toContain('Second disclaimer.');
    });

    it('hides trailing disclaimer completely on follow-up turns (isFollowupTurn=true)', () => {
      const message = {
        sender: 'assistant',
        text: 'Drink water to stay hydrated.\n\n**Disclaimer:** This is for educational purposes only.',
      };

      const { container } = render(<ChatMessage message={message} isFollowupTurn={true} />);
      expect(screen.getByText(/Drink water to stay hydrated/)).toBeInTheDocument();
      expect(container.textContent).not.toContain('Disclaimer:');
    });
  });
});
