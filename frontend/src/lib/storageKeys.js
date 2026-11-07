/**
 * Every localStorage / sessionStorage key the frontend reads or writes.
 * Keys prefixed `mediskye_` are wiped by clearLocalAuthStorage() on logout,
 * except the UI-preference keys listed in PRESERVED_STORAGE_KEYS (api.js).
 */
export const STORAGE_KEYS = {
  token: 'token',
  uiLang: 'mediskye_ui_lang',
  patientId: 'mediskye_patient_id',
  autoRead: 'mediskye_auto_read',
  sidebarOpen: 'mediskye_sidebar_open',
  theme: 'mediskye_theme',
  // New in the redesign (all UI-only; safe to clear on logout)
  inspectorOpen: 'mediskye_inspector_open',
  inspectorWidth: 'mediskye_inspector_width',
  inspectorTab: 'mediskye_inspector_tab',
  // sessionStorage
  consentPrompted: 'mediskye_consent_prompted',
};

export function readStorage(key, fallback = null) {
  try {
    const v = localStorage.getItem(key);
    return v === null ? fallback : v;
  } catch {
    return fallback;
  }
}

export function writeStorage(key, value) {
  try {
    localStorage.setItem(key, String(value));
    return true;
  } catch {
    return false;
  }
}
