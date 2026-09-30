import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import ChatMessage from '../components/ChatMessage';

describe('ChatMessage markdown rendering', () => {
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
});
