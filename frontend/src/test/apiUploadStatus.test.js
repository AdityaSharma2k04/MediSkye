import { afterEach, describe, expect, it, vi } from 'vitest';
import { getUploadStatus } from '../services/api';

describe('getUploadStatus', () => {
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('aborts a status request after its timeout', async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn((_url, { signal }) => new Promise((_resolve, reject) => {
      signal.addEventListener('abort', () => {
        reject(new DOMException('The operation was aborted.', 'AbortError'));
      });
    }));
    vi.stubGlobal('fetch', fetchMock);

    const request = getUploadStatus('job-timeout', 100);
    const requestRejection = expect(request).rejects.toThrow(/Request timed out/);
    await vi.advanceTimersByTimeAsync(100);

    await requestRejection;
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringContaining('/upload/status/job-timeout'),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
  });
});
