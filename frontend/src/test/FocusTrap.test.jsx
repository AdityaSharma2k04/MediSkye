import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React, { useRef, useState } from 'react';
import useFocusTrap from '../hooks/useFocusTrap';

function TestModal({ isOpen, onClose }) {
  const modalRef = useRef(null);
  useFocusTrap(modalRef, isOpen, onClose);

  if (!isOpen) return null;

  return (
    <div ref={modalRef} role="dialog">
      <button>Button 1</button>
      <button>Button 2</button>
      <button>Button 3</button>
    </div>
  );
}

describe('useFocusTrap', () => {
  it('focuses the first element when opened', () => {
    render(<TestModal isOpen={true} onClose={() => {}} />);
    const btn1 = screen.getByText('Button 1');
    expect(btn1).toHaveFocus();
  });

  it('cycles focus within modal on Tab and Shift+Tab', async () => {
    const user = userEvent.setup();
    render(<TestModal isOpen={true} onClose={() => {}} />);
    const btn1 = screen.getByText('Button 1');
    const btn2 = screen.getByText('Button 2');
    const btn3 = screen.getByText('Button 3');

    expect(btn1).toHaveFocus();

    // Tab -> Button 2
    await user.tab();
    expect(btn2).toHaveFocus();

    // Tab -> Button 3
    await user.tab();
    expect(btn3).toHaveFocus();

    // Tab from last element wraps back to Button 1
    await user.tab();
    expect(btn1).toHaveFocus();

    // Shift+Tab from first element wraps to Button 3
    await user.tab({ shift: true });
    expect(btn3).toHaveFocus();

    // Shift+Tab -> Button 2
    await user.tab({ shift: true });
    expect(btn2).toHaveFocus();
  });

  it('calls onClose when Escape key is pressed', async () => {
    const user = userEvent.setup();
    const handleClose = vi.fn();
    render(<TestModal isOpen={true} onClose={handleClose} />);

    await user.keyboard('{Escape}');
    expect(handleClose).toHaveBeenCalledTimes(1);
  });

  it('restores focus to trigger element upon closing', async () => {
    function ParentComponent() {
      const [open, setOpen] = useState(false);
      return (
        <div>
          <button id="open-btn" onClick={() => setOpen(true)}>Open Modal</button>
          <TestModal isOpen={open} onClose={() => setOpen(false)} />
        </div>
      );
    }

    const user = userEvent.setup();
    render(<ParentComponent />);

    const openBtn = screen.getByText('Open Modal');
    openBtn.focus();
    expect(openBtn).toHaveFocus();

    await user.click(openBtn);
    expect(screen.getByText('Button 1')).toHaveFocus();

    await user.keyboard('{Escape}');
    expect(openBtn).toHaveFocus();
  });
});
