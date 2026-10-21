import { describe, it, expect, vi, beforeEach } from 'vitest';
import { pickVoiceForLanguage, speakText, stopSpeaking } from '../services/speech';

// ── SpeechSynthesis mocks ────────────────────────────────────────────────
class FakeUtterance {
  constructor(text) {
    this.text = text;
    this.voice = null;
    this.lang = '';
    this.rate = 1;
    this.pitch = 1;
    this.onend = null;
    this.onerror = null;
  }
}

function installSpeechMocks() {
  const synth = {
    cancel: vi.fn(),
    speak: vi.fn(),
    getVoices: () => [
      { name: 'Hindi Voice', lang: 'hi-IN' },
      { name: 'US English', lang: 'en-US' },
      { name: 'British English', lang: 'en-GB' },
    ],
    addEventListener: vi.fn(),
  };
  Object.defineProperty(window, 'speechSynthesis', {
    value: synth,
    writable: true,
    configurable: true,
  });
  window.SpeechSynthesisUtterance = FakeUtterance;
  return synth;
}

describe('speech service — language-matched voices', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    installSpeechMocks();
  });

  it('picks hi-IN voice for Hindi', () => {
    const voice = pickVoiceForLanguage('Hindi');
    expect(voice).not.toBeNull();
    expect(voice.lang).toBe('hi-IN');
  });

  it('picks an English voice for English', () => {
    const voice = pickVoiceForLanguage('English');
    expect(voice).not.toBeNull();
    expect(voice.lang.toLowerCase()).toMatch(/^en/);
  });

  it('returns null when no matching voice exists', () => {
    expect(pickVoiceForLanguage('Spanish')).toBeNull();
  });

  it('speakText applies the Hindi voice and language', () => {
    speakText('Your hemoglobin is normal.', undefined, 'Hindi');
    const synth = window.speechSynthesis;
    expect(synth.cancel).toHaveBeenCalled();
    expect(synth.speak).toHaveBeenCalledTimes(1);
    const utterance = synth.speak.mock.calls[0][0];
    expect(utterance.lang).toBe('hi-IN');
    expect(utterance.voice.lang).toBe('hi-IN');
  });

  it('infers Hindi from the UI language preference when no language passed', () => {
    localStorage.setItem('mediskye_ui_lang', 'hi');
    speakText('Hello');
    const synth = window.speechSynthesis;
    const utterance = synth.speak.mock.calls[0][0];
    expect(utterance.lang).toBe('hi-IN');
  });

  it('cleans markdown syntax before speaking', () => {
    speakText('**Bold** value is `14.2` g/dL [read more](https://x.y)');
    const synth = window.speechSynthesis;
    const utterance = synth.speak.mock.calls[0][0];
    expect(utterance.text).not.toContain('**');
    expect(utterance.text).not.toContain('`');
    expect(utterance.text).not.toContain('(https://');
    expect(utterance.text).toContain('read more');
  });

  it('returns a speech token and dispatches start event', () => {
    const handler = vi.fn();
    window.addEventListener('mediskye:speechstart', handler);
    const token = speakText('Hello there');
    expect(typeof token).toBe('number');
    expect(handler).toHaveBeenCalledTimes(1);
    expect(handler.mock.calls[0][0].detail.token).toBe(token);
  });

  it('stopSpeaking cancels and dispatches the end event', () => {
    const endHandler = vi.fn();
    window.addEventListener('mediskye:speechend', endHandler);
    const token = speakText('Hello there');
    stopSpeaking();
    expect(window.speechSynthesis.cancel).toHaveBeenCalled();
    const endCalls = endHandler.mock.calls.filter((c) => c[0].detail.token === token);
    expect(endCalls.length).toBeGreaterThanOrEqual(1);
  });

  it('calls onEnd when the utterance finishes', () => {
    const onEnd = vi.fn();
    speakText('Hello', onEnd);
    const synth = window.speechSynthesis;
    const utterance = synth.speak.mock.calls[0][0];
    utterance.onend();
    expect(onEnd).toHaveBeenCalledTimes(1);
  });

  it('does not throw when text-to-speech is unavailable', () => {
    Object.defineProperty(window, 'speechSynthesis', { value: undefined, configurable: true });
    const onEnd = vi.fn();
    expect(() => speakText('Hello', onEnd)).not.toThrow();
    expect(onEnd).toHaveBeenCalled();
  });
});
