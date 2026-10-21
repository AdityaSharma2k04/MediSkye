/**
 * Safe localStorage wrapper that guards against:
 * 1. SecurityError (e.g. Safari Private Browsing mode with storage disabled)
 * 2. QuotaExceededError
 * 3. JSON parse errors and corrupted user preferences
 * 4. Invalid locale / theme values (fallbacks enforced)
 */

const SUPPORTED_LOCALES = new Set(['en', 'hi']);
const SUPPORTED_THEMES = new Set(['light', 'dark', 'system']);

export const safeStorage = {
  getItem(key, fallback = null) {
    try {
      if (typeof window === 'undefined' || !window.localStorage) return fallback;
      const val = window.localStorage.getItem(key);
      return val !== null ? val : fallback;
    } catch (e) {
      return fallback;
    }
  },

  setItem(key, value) {
    try {
      if (typeof window === 'undefined' || !window.localStorage) return false;
      window.localStorage.setItem(key, String(value));
      return true;
    } catch (e) {
      return false;
    }
  },

  removeItem(key) {
    try {
      if (typeof window === 'undefined' || !window.localStorage) return;
      window.localStorage.removeItem(key);
    } catch (e) {
      // ignore
    }
  },

  getJSON(key, fallback = null) {
    try {
      const item = this.getItem(key);
      if (!item) return fallback;
      return JSON.parse(item);
    } catch (e) {
      return fallback;
    }
  },

  setJSON(key, value) {
    try {
      return this.setItem(key, JSON.stringify(value));
    } catch (e) {
      return false;
    }
  },

  getValidLanguage() {
    const raw = this.getItem('mediskye_ui_lang');
    if (raw && SUPPORTED_LOCALES.has(raw.toLowerCase())) {
      return raw.toLowerCase();
    }
    return 'en';
  },

  getValidTheme() {
    const raw = this.getItem('mediskye_theme');
    if (raw && SUPPORTED_THEMES.has(raw.toLowerCase())) {
      return raw.toLowerCase();
    }
    return 'system';
  },
};
