import { useEffect, useLayoutEffect, useRef } from 'react';

/**
 * Custom hook to trap focus within a container element while isOpen is true,
 * restore focus to the previously active element upon closing, and handle the Escape key.
 *
 * Uses a persistent `focusin` listener to track the last element focused *outside*
 * the modal container, so that `autoFocus` children don't overwrite the trigger ref.
 */
export function useFocusTrap(ref, isOpen, onClose) {
  const triggerRef = useRef(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;
  const isOpenRef = useRef(isOpen);
  isOpenRef.current = isOpen;

  // Track the last focused element while the modal is CLOSED.
  // Once isOpen is true, freeze triggerRef so internal autoFocus inputs cannot overwrite it.
  useEffect(() => {
    const handleFocusIn = () => {
      if (isOpenRef.current) return;
      const active = document.activeElement;
      if (active && active !== document.body && (!ref.current || !ref.current.contains(active))) {
        triggerRef.current = active;
      }
    };
    document.addEventListener('focusin', handleFocusIn, true);
    return () => document.removeEventListener('focusin', handleFocusIn, true);
  }, [ref]);

  useLayoutEffect(() => {
    if (!isOpen) return;

    // Fallback: if triggerRef wasn't set by focusin before open, capture current activeElement if outside
    if (!triggerRef.current && document.activeElement && (!ref.current || !ref.current.contains(document.activeElement))) {
      triggerRef.current = document.activeElement;
    }

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
    // Only move focus into the modal if nothing inside already has focus (e.g. autoFocus)
    if (!ref.current.contains(document.activeElement) && focusable.length > 0) {
      focusable[0].focus();
    }

    const handleKeyDown = (e) => {
      if (e.key === 'Escape' && onCloseRef.current) {
        e.preventDefault();
        onCloseRef.current();
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
      // Restore focus to the element that triggered the modal
      const target = triggerRef.current;
      if (target && typeof target.focus === 'function' && document.body.contains(target)) {
        target.focus({ preventScroll: true });
      }
    };
  }, [isOpen, ref]);
}

export default useFocusTrap;
