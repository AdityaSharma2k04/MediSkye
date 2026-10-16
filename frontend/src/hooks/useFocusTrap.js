import { useEffect, useRef } from 'react';

/**
 * Custom hook to trap focus within a container element while isOpen is true,
 * restore focus to the previously active element upon closing, and handle the Escape key.
 */
export function useFocusTrap(ref, isOpen, onClose) {
  const triggerRef = useRef(null);

  useEffect(() => {
    if (!isOpen) return;

    // Remember the element that had focus before opening the modal
    triggerRef.current = document.activeElement;

    if (!ref.current) return;

    const getFocusable = () => {
      if (!ref.current) return [];
      return Array.from(
        ref.current.querySelectorAll(
          'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
        )
      );
    };

    const focusable = getFocusable();
    if (focusable.length > 0) {
      focusable[0].focus();
    }

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && onClose) {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key !== 'Tab') return;

      const currentFocusable = getFocusable();
      if (currentFocusable.length === 0) return;

      const first = currentFocusable[0];
      const last = currentFocusable[currentFocusable.length - 1];

      if (e.shiftKey) {
        if (document.activeElement === first || !ref.current.contains(document.activeElement)) {
          e.preventDefault();
          last.focus();
        }
      } else {
        if (document.activeElement === last || !ref.current.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener('keydown', handleKeyDown);

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      // Restore focus to trigger element on close
      if (triggerRef.current && typeof triggerRef.current.focus === 'function') {
        triggerRef.current.focus();
      }
    };
  }, [isOpen, ref, onClose]);
}

export default useFocusTrap;
