import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  isJwtExpiredOrExpiringSoon,
  getAuthToken,
  apiFetch,
} from '../services/api';
import {
  touchAuthActivity,
  isSessionExpiredByInactivity,
  getSavedAuthSession,
  saveAuthSession,
  performExplicitLogout,
  clearSavedAuthSession,
  FIFTEEN_DAYS_MS,
  auth,
} from '../services/firebase';

describe('15-Day Rolling Inactivity Session & Token Lifecycle', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  describe('isSessionExpiredByInactivity & 15-day rolling timer', () => {
    it('initializes mediskye_auth_last_active if missing and returns false (never boots active user)', () => {
      expect(localStorage.getItem('mediskye_auth_last_active')).toBeNull();
      const expired = isSessionExpiredByInactivity();
      expect(expired).toBe(false);
      expect(localStorage.getItem('mediskye_auth_last_active')).toBeTruthy();
    });

    it('returns false for an active user within 15 days (e.g. active 3 days ago)', () => {
      const threeDaysAgo = Date.now() - 3 * 24 * 60 * 60 * 1000;
      localStorage.setItem('mediskye_auth_last_active', String(threeDaysAgo));
      expect(isSessionExpiredByInactivity()).toBe(false);
    });

    it('returns true when user has been inactive for >15 days (e.g. 16 days ago)', () => {
      const sixteenDaysAgo = Date.now() - 16 * 24 * 60 * 60 * 1000;
      localStorage.setItem('mediskye_auth_last_active', String(sixteenDaysAgo));
      expect(isSessionExpiredByInactivity()).toBe(true);
    });

    it('touchAuthActivity rolls forward the 15-day inactivity window', () => {
      const tenDaysAgo = Date.now() - 10 * 24 * 60 * 60 * 1000;
      localStorage.setItem('mediskye_auth_last_active', String(tenDaysAgo));
      touchAuthActivity();
      const updated = Number(localStorage.getItem('mediskye_auth_last_active'));
      expect(Date.now() - updated).toBeLessThan(1000);
      expect(isSessionExpiredByInactivity()).toBe(false);
    });
  });

  describe('getSavedAuthSession & saveAuthSession', () => {
    it('saves and retrieves active auth session when within 15 days', () => {
      const mockUser = {
        uid: 'user_123',
        email: 'alex@example.com',
        displayName: 'Alex Carter',
        photoURL: null,
      };
      saveAuthSession(mockUser, 'test-token-123');
      expect(localStorage.getItem('mediskye_explicit_logout')).toBeNull();
      expect(localStorage.getItem('token')).toBe('test-token-123');

      const saved = getSavedAuthSession();
      expect(saved).toEqual({
        uid: 'user_123',
        email: 'alex@example.com',
        displayName: 'Alex Carter',
        photoURL: null,
      });
    });

    it('returns null and purges session if user has been inactive for 16 days (>15 days)', () => {
      const mockUser = { uid: 'user_old', email: 'old@example.com' };
      saveAuthSession(mockUser, 'old-token');
      const sixteenDaysAgo = Date.now() - 16 * 24 * 60 * 60 * 1000;
      localStorage.setItem('mediskye_auth_last_active', String(sixteenDaysAgo));

      const saved = getSavedAuthSession();
      expect(saved).toBeNull();
      expect(localStorage.getItem('mediskye_auth_user_snapshot')).toBeNull();
      expect(localStorage.getItem('token')).toBeNull();
    });

    it('returns null if user explicitly logged out (mediskye_explicit_logout === 1)', async () => {
      const mockUser = { uid: 'user_456', email: 'user@test.com' };
      saveAuthSession(mockUser, 'tok-456');

      await performExplicitLogout();
      expect(localStorage.getItem('mediskye_explicit_logout')).toBe('1');
      expect(getSavedAuthSession()).toBeNull();
    });
  });

  describe('isJwtExpiredOrExpiringSoon', () => {
    it('returns true for malformed, null, or non-jwt strings', () => {
      expect(isJwtExpiredOrExpiringSoon(null)).toBe(true);
      expect(isJwtExpiredOrExpiringSoon('')).toBe(true);
      expect(isJwtExpiredOrExpiringSoon('not-a-jwt')).toBe(true);
    });

    it('returns true for expired JWT (exp in the past)', () => {
      const pastExp = Math.floor(Date.now() / 1000) - 300;
      const expiredJwt = `header.${btoa(JSON.stringify({ exp: pastExp }))}.sig`;
      expect(isJwtExpiredOrExpiringSoon(expiredJwt)).toBe(true);
    });

    it('returns true for JWT expiring within buffer window (e.g. 2 minutes remaining with 300s buffer)', () => {
      const soonExp = Math.floor(Date.now() / 1000) + 120; // 2 minutes left
      const soonJwt = `header.${btoa(JSON.stringify({ exp: soonExp }))}.sig`;
      expect(isJwtExpiredOrExpiringSoon(soonJwt, 300)).toBe(true);
    });

    it('returns false for fresh JWT expiring in 50 minutes', () => {
      const freshExp = Math.floor(Date.now() / 1000) + 3000; // 50 mins left
      const freshJwt = `header.${btoa(JSON.stringify({ exp: freshExp }))}.sig`;
      expect(isJwtExpiredOrExpiringSoon(freshJwt, 300)).toBe(false);
    });
  });

  describe('getAuthToken Live Refresh', () => {
    it('refreshes token via getIdToken(true) when cached token is expiring or expired', async () => {
      const expiredExp = Math.floor(Date.now() / 1000) - 60;
      const expiredJwt = `header.${btoa(JSON.stringify({ exp: expiredExp }))}.sig`;
      localStorage.setItem('mediskye_auth_id_token', expiredJwt);
      localStorage.setItem('token', expiredJwt);

      const freshJwt = `header.${btoa(JSON.stringify({ exp: Math.floor(Date.now() / 1000) + 3600 }))}.sig`;
      const getIdTokenMock = vi.fn().mockResolvedValue(freshJwt);
      auth.currentUser = { getIdToken: getIdTokenMock };

      const token = await getAuthToken();
      expect(getIdTokenMock).toHaveBeenCalledWith(true);
      expect(token).toBe(freshJwt);
      expect(localStorage.getItem('token')).toBe(freshJwt);
      expect(localStorage.getItem('mediskye_auth_id_token')).toBe(freshJwt);
    });

    it('falls back to cached token if auth.currentUser is null (e.g. offline boot)', async () => {
      auth.currentUser = null;
      localStorage.setItem('token', 'offline-cached-token');
      const token = await getAuthToken();
      expect(token).toBe('offline-cached-token');
    });
  });

  describe('apiFetch 401 & Network Error Protection', () => {
    it('retries once with refreshed token on 401 and NEVER deletes mediskye_auth_user_snapshot', async () => {
      const snap = { uid: 'user_live', email: 'live@test.com' };
      localStorage.setItem('mediskye_auth_user_snapshot', JSON.stringify(snap));
      localStorage.setItem('token', 'old-token');

      const freshToken = 'refreshed-jwt-token';
      auth.currentUser = {
        getIdToken: vi.fn().mockResolvedValue(freshToken),
      };

      let callCount = 0;
      global.fetch = vi.fn().mockImplementation(async (url, opts) => {
        callCount += 1;
        if (callCount === 1) {
          return { status: 401, ok: false };
        }
        return {
          status: 200,
          ok: true,
          json: async () => ({ success: true }),
        };
      });

      const res = await apiFetch('http://localhost:8000/test-endpoint');
      expect(res.ok).toBe(true);
      expect(callCount).toBe(2);
      expect(auth.currentUser.getIdToken).toHaveBeenCalledWith(true);
      // User snapshot must NEVER be wiped
      expect(localStorage.getItem('mediskye_auth_user_snapshot')).toBeTruthy();
    });

    it('throws on permanent 401 but still NEVER wipes mediskye_auth_user_snapshot or token', async () => {
      const snap = { uid: 'user_live', email: 'live@test.com' };
      localStorage.setItem('mediskye_auth_user_snapshot', JSON.stringify(snap));
      localStorage.setItem('token', 'failing-token');

      auth.currentUser = {
        getIdToken: vi.fn().mockResolvedValue('failing-token-2'),
      };

      global.fetch = vi.fn().mockResolvedValue({
        status: 401,
        ok: false,
      });

      await expect(apiFetch('http://localhost:8000/test-401')).rejects.toThrow();

      // Snapshot MUST be preserved across 401 errors
      expect(localStorage.getItem('mediskye_auth_user_snapshot')).toBeTruthy();
      expect(JSON.parse(localStorage.getItem('mediskye_auth_user_snapshot')).uid).toBe('user_live');
    });
  });
});
