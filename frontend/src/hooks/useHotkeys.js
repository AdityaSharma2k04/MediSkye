import { useEffect, useRef } from 'react';

const isMac = () => typeof navigator !== 'undefined' && /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent || '');

export const MOD_LABEL = isMac() ? '⌘' : 'Ctrl';

/**
 * Parse "mod+k", "mod+shift+e", "alt+1", "/", "escape".
 * `mod` is Ctrl on Windows/Linux/Android and ⌘ on macOS.
 */
function matches(event, combo) {
  const parts = combo.toLowerCase().split('+').map((p) => p.trim());
  const key = parts[parts.length - 1];
  const wantMod = parts.includes('mod');
  const wantShift = parts.includes('shift');
  const wantAlt = parts.includes('alt');
  const modPressed = isMac() ? event.metaKey : event.ctrlKey;

  if (wantMod !== modPressed) return false;
  if (wantShift !== event.shiftKey) return false;
  if (wantAlt !== event.altKey) return false;

  const evKey = (event.key || '').toLowerCase();
  if (key === 'escape') return evKey === 'escape' || evKey === 'esc';
  if (key === 'slash' || key === '/') return evKey === '/';
  if (key === 'backslash' || key === '\\') return evKey === '\\';
  if (/^\d$/.test(key)) return evKey === key || event.code === `Digit${key}`;
  return evKey === key || event.code?.toLowerCase() === `key${key}`;
}

function isTypingTarget(el) {
  if (!el) return false;
  const tag = el.tagName;
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable;
}

/**
 * Register global keyboard shortcuts.
 * @param {Array<{combo: string, handler: (e: KeyboardEvent) => void, allowInInput?: boolean, enabled?: boolean}>} bindings
 */
export default function useHotkeys(bindings) {
  const ref = useRef(bindings);
  ref.current = bindings;

  useEffect(() => {
    const onKeyDown = (event) => {
      const list = ref.current || [];
      for (const b of list) {
        if (b.enabled === false) continue;
        if (!matches(event, b.combo)) continue;
        const hasModifier = event.ctrlKey || event.metaKey || event.altKey;
        if (!b.allowInInput && !hasModifier && isTypingTarget(event.target)) continue;
        event.preventDefault();
        b.handler(event);
        return;
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, []);
}
