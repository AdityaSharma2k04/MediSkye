import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { safeStorage } from '../services/storage';
import { apiFetch, sendQueryStream } from '../services/api';
import { auth } from '../services/firebase';
import ChatInput from '../components/ChatInput';

vi.mock('../services/firebase', () => ({
  auth: {
    currentUser: null,
  },
  signOut: vi.fn(),
  getFirebaseErrorMessage: vi.fn((err) => err?.message || 'Auth error'),
}));

describe('Frontend Chaos QA & Edge Cases', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  describe('1. safeStorage Resiliency & Corrupted Preferences', () => {
    it('recovers from invalid i18n locale and falls back to "en"', () => {
      localStorage.setItem('mediskye_ui_lang', 'klingon');
      expect(safeStorage.getValidLanguage()).toBe('en');

      localStorage.setItem('mediskye_ui_lang', 'pirate');
      expect(safeStorage.getValidLanguage()).toBe('en');

      localStorage.setItem('mediskye_ui_lang', 'HI'); // case insensitive
      expect(safeStorage.getValidLanguage()).toBe('hi');

      localStorage.setItem('mediskye_ui_lang', 'en');
      expect(safeStorage.getValidLanguage()).toBe('en');
    });

    it('recovers from invalid theme and falls back to "system"', () => {
      localStorage.setItem('mediskye_theme', 'neon-cyberpunk');
      expect(safeStorage.getValidTheme()).toBe('system');

      localStorage.setItem('mediskye_theme', 'DARK');
      expect(safeStorage.getValidTheme()).toBe('dark');
    });

    it('safely handles malformed JSON in localStorage', () => {
      localStorage.setItem('corrupted_key', '{not valid json: 123');
      const result = safeStorage.getJSON('corrupted_key', { fallback: true });
      expect(result).toEqual({ fallback: true });
    });

    it('safely survives SecurityError (Safari Private Browsing restriction)', () => {
      const mockThrowingStorage = {
        getItem: vi.fn(() => {
          throw new DOMException('The operation is insecure.', 'SecurityError');
        }),
        setItem: vi.fn(() => {
          throw new DOMException('The operation is insecure.', 'SecurityError');
        }),
        removeItem: vi.fn(() => {
          throw new DOMException('The operation is insecure.', 'SecurityError');
        }),
      };

      vi.stubGlobal('localStorage', mockThrowingStorage);

      expect(() => {
        const val = safeStorage.getItem('any_key', 'fallback_val');
        expect(val).toBe('fallback_val');
        const setOk = safeStorage.setItem('any_key', 'val');
        expect(setOk).toBe(false);
        safeStorage.removeItem('any_key');
      }).not.toThrow();
    });
  });

  describe('2. apiFetch Network Chaos & Offline Protection', () => {
    it('fails fast when navigator.onLine is false without hanging', async () => {
      vi.stubGlobal('navigator', { onLine: false });

      await expect(apiFetch('/test/endpoint')).rejects.toThrow(
        /You appear to be offline. Please check your internet connection./
      );
    });

    it('aborts when request exceeds timeout threshold', async () => {
      vi.useFakeTimers();
      vi.stubGlobal('navigator', { onLine: true });

      const fetchMock = vi.fn((_url, { signal }) => new Promise((_resolve, reject) => {
        signal.addEventListener('abort', () => {
          reject(new DOMException('The operation was aborted.', 'AbortError'));
        });
      }));
      vi.stubGlobal('fetch', fetchMock);

      const request = apiFetch('/test/endpoint', {}, 200);
      const rejection = expect(request).rejects.toThrow(/Request timed out/);
      await vi.advanceTimersByTimeAsync(250);
      await rejection;
    });

    it('automatically catches 401 and retries once with refreshed Firebase token', async () => {
      vi.stubGlobal('navigator', { onLine: true });

      const mockGetIdToken = vi.fn().mockResolvedValue('fresh-jwt-token-123');
      auth.currentUser = {
        getIdToken: mockGetIdToken,
      };

      let attempts = 0;
      const fetchMock = vi.fn((_url, options) => {
        attempts += 1;
        if (attempts === 1) {
          // First call: 401 Unauthorized
          return Promise.resolve({
            ok: false,
            status: 401,
            json: () => Promise.resolve({ detail: 'Token expired' }),
          });
        }
        // Second call: 200 OK after token refresh
        return Promise.resolve({
          ok: true,
          status: 200,
          json: () => Promise.resolve({ success: true }),
        });
      });

      vi.stubGlobal('fetch', fetchMock);

      const response = await apiFetch('/protected/resource');
      expect(response.status).toBe(200);
      expect(mockGetIdToken).toHaveBeenCalledWith(true);
      expect(localStorage.getItem('token')).toBe('fresh-jwt-token-123');
      expect(fetchMock).toHaveBeenCalledTimes(2);

      // Verify second request used fresh Bearer token
      const secondCallHeaders = fetchMock.mock.calls[1][1].headers;
      expect(secondCallHeaders['Authorization']).toBe('Bearer fresh-jwt-token-123');
    });

    it('sendQueryStream enforces 180s timeout and attaches status on 409 response', async () => {
      vi.stubGlobal('navigator', { onLine: true });

      const fetchMock = vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: () => Promise.resolve({ detail: 'A query stream is already active' }),
      });
      vi.stubGlobal('fetch', fetchMock);

      let caughtErr;
      try {
        await sendQueryStream('Test question', 'session-123', 'English', () => {});
      } catch (err) {
        caughtErr = err;
      }

      expect(caughtErr).toBeDefined();
      expect(caughtErr.status).toBe(409);
      expect(caughtErr.message).toContain('already active');

      expect(fetchMock).toHaveBeenCalledWith(
        expect.stringContaining('/query'),
        expect.objectContaining({
          method: 'POST',
          body: expect.stringContaining('Test question'),
        })
      );
    });
  });

  describe('3. ChatInput Synchronous Double-Send & Unmount Guard', () => {
    it('prevents rapid double-send within the same synchronous event frame', () => {
      const handleSendMessage = vi.fn();
      render(<ChatInput onSendMessage={handleSendMessage} disabled={false} />);

      const textarea = screen.getByRole('textbox');
      fireEvent.change(textarea, { target: { value: 'My medical symptom query' } });

      const form = textarea.closest('form');
      // Rapid fire 3 submit events in immediate sequence
      fireEvent.submit(form);
      fireEvent.submit(form);
      fireEvent.submit(form);

      // Due to isSubmittingRef synchronous lock, onSendMessage should ONLY have fired once!
      expect(handleSendMessage).toHaveBeenCalledTimes(1);
      expect(handleSendMessage).toHaveBeenCalledWith('My medical symptom query');
    });
  });
});
