import { describe, it, expect, vi } from 'vitest';
import { parseSSEStream } from '../services/api';

function createMockReader(chunks) {
  const encoder = new TextEncoder();
  let index = 0;
  return {
    read: async () => {
      if (index >= chunks.length) {
        return { done: true, value: undefined };
      }
      const value = encoder.encode(chunks[index++]);
      return { done: false, value };
    },
  };
}

describe('parseSSEStream', () => {
  it('parses multi-line SSE with event: stage and data: tokens', async () => {
    const ssePayload =
      'event: stage\n' +
      'data: {"stage": "analyzing", "message": "Analyzing your question..."}\n\n' +
      'event: stage\n' +
      'data: {"stage": "generating", "message": "Preparing your answer..."}\n\n' +
      'data: {"token": "Your "}\n\n' +
      'data: [DONE]\n\n';

    const reader = createMockReader([ssePayload]);
    const onStage = vi.fn();
    const onContent = vi.fn();

    await parseSSEStream(reader, { onStage, onContent });

    expect(onStage).toHaveBeenCalledTimes(2);
    expect(onStage).toHaveBeenNthCalledWith(1, {
      stage: 'analyzing',
      message: 'Analyzing your question...',
    });
    expect(onStage).toHaveBeenNthCalledWith(2, {
      stage: 'generating',
      message: 'Preparing your answer...',
    });

    expect(onContent).toHaveBeenCalledTimes(1);
    expect(onContent).toHaveBeenCalledWith({ token: 'Your ' });
  });

  it('routes to unified onChunk function when passed as callback', async () => {
    const ssePayload =
      'event: stage\n' +
      'data: {"stage": "searching", "message": "Searching reports..."}\n\n' +
      'data: {"chunk": "Test token"}\n\n' +
      'data: [DONE]\n\n';

    const reader = createMockReader([ssePayload]);
    const onChunk = vi.fn();

    await parseSSEStream(reader, onChunk);

    expect(onChunk).toHaveBeenCalledTimes(2);
    expect(onChunk).toHaveBeenNthCalledWith(1, {
      stage: 'searching',
      message: 'Searching reports...',
    });
    expect(onChunk).toHaveBeenNthCalledWith(2, {
      chunk: 'Test token',
    });
  });

  it('throws an error if the stream closes without a [DONE] or error chunk', async () => {
    const ssePayload =
      'event: stage\n' +
      'data: {"stage": "analyzing", "message": "Analyzing..."}\n\n' +
      'data: {"token": "Incomplete response..."}\n\n';

    const reader = createMockReader([ssePayload]);
    const onChunk = vi.fn();

    await expect(parseSSEStream(reader, onChunk)).rejects.toThrow(/interrupted/i);
  });

  it('treats data with error as a valid terminal event even without [DONE]', async () => {
    const ssePayload =
      'data: {"error": "LLM model overloaded"}\n\n';

    const reader = createMockReader([ssePayload]);
    const onChunk = vi.fn();

    await expect(parseSSEStream(reader, onChunk)).resolves.not.toThrow();
    expect(onChunk).toHaveBeenCalledWith({ error: 'LLM model overloaded' });
  });
});
