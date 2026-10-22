import { useEffect, useRef, useState } from 'react';

/**
 * Lightweight IntersectionObserver hook for triggering scroll animations.
 * Automatically adds and preserves visibility state once observed.
 */
export function useIntersectionObserver(options = {}) {
  const elementRef = useRef(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const element = elementRef.current;
    if (!element) return;

    // Gracefully handle environments without IntersectionObserver (e.g., jsdom / older browsers)
    if (typeof window === 'undefined' || !('IntersectionObserver' in window)) {
      setIsVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          if (options.triggerOnce !== false) {
            observer.unobserve(entry.target);
          }
        } else if (options.triggerOnce === false) {
          setIsVisible(false);
        }
      },
      {
        threshold: options.threshold ?? 0.15,
        root: options.root ?? null,
        rootMargin: options.rootMargin ?? '0px',
      }
    );

    observer.observe(element);

    return () => {
      observer.disconnect();
    };
  }, [options.threshold, options.root, options.rootMargin, options.triggerOnce]);

  return [elementRef, isVisible];
}

export default useIntersectionObserver;
