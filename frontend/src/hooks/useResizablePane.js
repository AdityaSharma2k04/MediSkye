import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { readStorage, writeStorage } from '../lib/storageKeys';

/**
 * Drag-to-resize for the right-hand inspector pane.
 * Width is measured from the right edge of the container and persisted.
 * Keyboard: ←/→ on the focused handle nudge by 24px, Home/End snap to bounds.
 */
export default function useResizablePane({ storageKey, defaultWidth = 440, min = 340, max = 760, containerRef, active = true }) {
  const [width, setWidth] = useState(() => {
    const stored = parseInt(readStorage(storageKey, ''), 10);
    return Number.isFinite(stored) ? Math.min(max, Math.max(min, stored)) : defaultWidth;
  });
  const [isDragging, setIsDragging] = useState(false);
  const widthRef = useRef(width);
  widthRef.current = width;

  const clampToContainer = useCallback(
    (w) => {
      const containerW = containerRef?.current?.getBoundingClientRect?.().width || window.innerWidth;
      // Always leave at least 420px for the conversation column
      const dynamicMax = Math.max(min, Math.min(max, containerW - 420));
      return Math.round(Math.min(dynamicMax, Math.max(min, w)));
    },
    [containerRef, min, max]
  );

  const persist = useCallback((w) => writeStorage(storageKey, w), [storageKey]);

  const onPointerDown = useCallback(
    (e) => {
      if (e.button !== undefined && e.button !== 0) return;
      e.preventDefault();
      const handle = e.currentTarget;
      try {
        handle.setPointerCapture?.(e.pointerId);
      } catch {
        /* pointer capture unsupported */
      }
      setIsDragging(true);
      const rect = containerRef?.current?.getBoundingClientRect?.();
      const right = rect ? rect.right : window.innerWidth;

      const onMove = (ev) => setWidth(clampToContainer(right - ev.clientX));
      const onUp = () => {
        setIsDragging(false);
        persist(widthRef.current);
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        window.removeEventListener('pointercancel', onUp);
      };
      window.addEventListener('pointermove', onMove);
      window.addEventListener('pointerup', onUp);
      window.addEventListener('pointercancel', onUp);
    },
    [clampToContainer, containerRef, persist]
  );

  const onKeyDown = useCallback(
    (e) => {
      let next = null;
      if (e.key === 'ArrowLeft') next = widthRef.current + 24;
      else if (e.key === 'ArrowRight') next = widthRef.current - 24;
      else if (e.key === 'Home') next = max;
      else if (e.key === 'End') next = min;
      if (next === null) return;
      e.preventDefault();
      const w = clampToContainer(next);
      setWidth(w);
      persist(w);
    },
    [clampToContainer, max, min, persist]
  );

  const reset = useCallback(() => {
    const w = clampToContainer(defaultWidth);
    setWidth(w);
    persist(w);
  }, [clampToContainer, defaultWidth, persist]);

  // Clamp as soon as the pane becomes visible (stored widths may not fit this window)
  useLayoutEffect(() => {
    if (active) setWidth((w) => clampToContainer(w));
  }, [active, clampToContainer]);

  // Re-clamp when the window shrinks
  useEffect(() => {
    const onResize = () => setWidth((w) => clampToContainer(w));
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, [clampToContainer]);

  useEffect(() => {
    if (!isDragging) return undefined;
    const prevCursor = document.body.style.cursor;
    const prevSelect = document.body.style.userSelect;
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
    return () => {
      document.body.style.cursor = prevCursor;
      document.body.style.userSelect = prevSelect;
    };
  }, [isDragging]);

  return {
    width,
    isDragging,
    reset,
    handleProps: {
      onPointerDown,
      onKeyDown,
      onDoubleClick: reset,
      role: 'separator',
      'aria-orientation': 'vertical',
      'aria-label': 'Resize inspector panel',
      'aria-valuenow': width,
      'aria-valuemin': min,
      'aria-valuemax': max,
      tabIndex: 0,
    },
  };
}
