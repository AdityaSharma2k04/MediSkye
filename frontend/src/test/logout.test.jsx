import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { logout } from '../services/api';

describe('logout() local storage hygiene', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    global.fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('clears token, every PHI-bearing mediskye_* key, and the session consent flag', async () => {
    localStorage.setItem('token', 'jwt-abc');
    localStorage.setItem('mediskye_session_id', 'sess-1');
    localStorage.setItem('mediskye_conversations', '[]');
    localStorage.setItem('mediskye_conversations_user-1', '[]');
    localStorage.setItem('mediskye_patient_id', 'dep-1');
    localStorage.setItem('mediskye_user_email', 'a@b.com');
    localStorage.setItem('mediskye_last_active_user', 'user-1');
    localStorage.setItem('mediskye_theme', 'dark');
    localStorage.setItem('mediskye_language', 'Spanish');
    localStorage.setItem('mediskye_sidebar_open', 'true');
    sessionStorage.setItem('mediskye_consent_prompted', 'true');
    // A non-app key must survive the purge.
    localStorage.setItem('unrelated_key', 'keep-me');

    await logout();

    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('mediskye_session_id')).toBeNull();
    expect(localStorage.getItem('mediskye_conversations')).toBeNull();
    expect(localStorage.getItem('mediskye_conversations_user-1')).toBeNull();
    expect(localStorage.getItem('mediskye_patient_id')).toBeNull();
    expect(localStorage.getItem('mediskye_user_email')).toBeNull();
    expect(localStorage.getItem('mediskye_last_active_user')).toBeNull();
    expect(localStorage.getItem('mediskye_sidebar_open')).toBeNull();
    expect(sessionStorage.getItem('mediskye_consent_prompted')).toBeNull();
    expect(localStorage.getItem('unrelated_key')).toBe('keep-me');
  });

  it('preserves UI preferences (theme, language) across logout', async () => {
    localStorage.setItem('token', 'jwt-abc');
    localStorage.setItem('mediskye_theme', 'system');
    localStorage.setItem('mediskye_language', 'Spanish');

    await logout();

    // Prefs are not auth/PHI state — they must survive to avoid a re-login flash.
    expect(localStorage.getItem('mediskye_theme')).toBe('system');
    expect(localStorage.getItem('mediskye_language')).toBe('Spanish');
    // Auth state is still purged.
    expect(localStorage.getItem('token')).toBeNull();
  });

  it('still purges local state when the server logout call rejects', async () => {
    localStorage.setItem('token', 'jwt-abc');
    localStorage.setItem('mediskye_conversations', '[]');
    global.fetch = vi.fn().mockRejectedValue(new Error('network down'));

    await logout();

    expect(localStorage.getItem('token')).toBeNull();
    expect(localStorage.getItem('mediskye_conversations')).toBeNull();
  });
});
