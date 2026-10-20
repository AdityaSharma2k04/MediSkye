import { afterEach, describe, expect, it, vi } from 'vitest';
import { deleteDocument, detachChatDocument } from '../services/api';

describe('deleteDocument API', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('calls DELETE /users/me/documents/{documentId}', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: vi.fn(),
    });
    vi.stubGlobal('fetch', fetchMock);

    const docId = '12345678-1234-1234-1234-123456789abc';
    const result = await deleteDocument(docId);

    expect(result).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(new RegExp(`/users/me/documents/${docId}$`)),
      expect.objectContaining({
        method: 'DELETE',
      })
    );
  });

  it('detachChatDocument delegates to deleteDocument and targets /users/me/documents', async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      status: 204,
      json: vi.fn(),
    });
    vi.stubGlobal('fetch', fetchMock);

    const chatId = 'chat-999';
    const docId = 'doc-888';
    const result = await detachChatDocument(chatId, docId);

    expect(result).toBe(true);
    expect(fetchMock).toHaveBeenCalledWith(
      expect.stringMatching(new RegExp(`/users/me/documents/${docId}$`)),
      expect.objectContaining({
        method: 'DELETE',
      })
    );
  });
});
