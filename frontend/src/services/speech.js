// Speech Service - Web Speech API (Voice-to-Text & Text-to-Speech)
import { logger } from './logger';

// ── Text-to-Speech (elevated) ─────────────────────────────────────────

// Language → preferred BCP-47 voice prefixes (best match first).
const VOICE_PREFIXES = {
  Hindi: ['hi-IN', 'hi'],
  English: ['en-IN', 'en-US', 'en-GB', 'en'],
  Spanish: ['es-ES', 'es-US', 'es-MX', 'es'],
  French: ['fr-FR', 'fr-CA', 'fr'],
  German: ['de-DE', 'de'],
};

// Voice list loads asynchronously in most browsers — warm a cache whenever
// the browser signals availability.
let cachedVoices = [];
function refreshVoices() {
  try {
    const voices = window.speechSynthesis?.getVoices?.();
    if (Array.isArray(voices)) cachedVoices = voices;
  } catch (e) {
    // ignore
  }
}
if (typeof window !== 'undefined') {
  refreshVoices();
  window.speechSynthesis?.addEventListener?.('voiceschanged', refreshVoices);
}

function inferLanguagePreference() {
  try {
    // 1. AI response language persisted by the settings flow
    const storedLang = localStorage.getItem('mediskye_language');
    if (storedLang && VOICE_PREFIXES[storedLang]) return storedLang;
    // 2. UI language (i18n) — 'hi' means the user reads/writes Hindi
    const uiLang = localStorage.getItem('mediskye_ui_lang');
    if (uiLang === 'hi') return 'Hindi';
  } catch (e) {
    // ignore
  }
  return 'English';
}

function normalizeLangTag(lang) {
  return String(lang || '').toLowerCase().replace('_', '-');
}

export function pickVoiceForLanguage(language) {
  refreshVoices();
  if (!cachedVoices.length) return null;
  const targets = VOICE_PREFIXES[language] || [];
  if (!targets.length) return null;
  for (const target of targets) {
    const match = cachedVoices.find((v) =>
      v && normalizeLangTag(v.lang).startsWith(target.toLowerCase())
    );
    if (match) return match;
  }
  return null;
}

let activeToken = 0;

function dispatchSpeechEvent(name, token) {
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent(name, { detail: { token } }));
  }
}

function speechSupported() {
  return (
    typeof window !== 'undefined' &&
    'speechSynthesis' in window &&
    Boolean(window.speechSynthesis)
  );
}

/**
 * Speak text aloud using the browser's native SpeechSynthesisUtterance.
 * Picks a voice matching the requested language (hi-IN for Hindi,
 * en-IN/en-US for English, etc.).
 *
 * @returns {number} a token identifying this speech session (for events).
 */
export function speakText(text, onEnd, language) {
  if (!speechSupported()) {
    logger.warn('Text-to-speech is not supported in this browser.');
    if (onEnd) onEnd();
    return null;
  }

  window.speechSynthesis.cancel(); // stop previous speaking
  dispatchSpeechEvent('mediskye:speechend', activeToken);

  // Clean markdown syntax for smooth reading
  const cleanText = text
    .replace(/[*#_~`>]/g, '')
    .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1') // [label](url) → label
    .replace(/\[\d+\]/g, '')
    .replace(/\s+/g, ' ')
    .trim();

  if (!cleanText) {
    if (onEnd) onEnd();
    return null;
  }

  const resolvedLanguage = language || inferLanguagePreference();
  const voice = pickVoiceForLanguage(resolvedLanguage);

  const utterance = new SpeechSynthesisUtterance(cleanText);
  if (voice) {
    utterance.voice = voice;
    utterance.lang = voice.lang;
  } else if (resolvedLanguage && VOICE_PREFIXES[resolvedLanguage]) {
    utterance.lang = VOICE_PREFIXES[resolvedLanguage][0];
  }
  utterance.rate = 1.0;
  utterance.pitch = 1.0;

  const token = ++activeToken;

  const finish = () => {
    if (activeToken === token) {
      activeToken = 0;
      dispatchSpeechEvent('mediskye:speechend', token);
    }
    if (onEnd) onEnd();
  };
  utterance.onend = finish;
  utterance.onerror = finish;

  window.speechSynthesis.speak(utterance);
  dispatchSpeechEvent('mediskye:speechstart', token);
  return token;
}

export function stopSpeaking() {
  if (speechSupported()) {
    window.speechSynthesis.cancel();
  }
  if (activeToken) {
    const token = activeToken;
    activeToken = 0;
    dispatchSpeechEvent('mediskye:speechend', token);
  }
}

// ── Speech-to-Text (unchanged) ────────────────────────────────────────

const SPEECH_RECOGNITION_LOCALE_MAP = {
  Hindi: 'hi-IN',
  hi: 'hi-IN',
  Spanish: 'es-ES',
  es: 'es-ES',
  French: 'fr-FR',
  fr: 'fr-FR',
  German: 'de-DE',
  de: 'de-DE',
  English: 'en-US',
  en: 'en-US',
};

export function startSpeechRecognition(onResult, onError, onEnd, lang) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    onError('Speech recognition is not supported in this browser.');
    return null;
  }

  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = true;

  const targetLang = lang || inferLanguagePreference();
  recognition.lang = SPEECH_RECOGNITION_LOCALE_MAP[targetLang] || (targetLang && targetLang.includes('-') ? targetLang : 'en-US');

  recognition.onresult = (event) => {
    let transcript = '';
    for (let i = event.resultIndex; i < event.results.length; i++) {
      transcript += event.results[i][0].transcript;
    }
    onResult(transcript);
  };

  recognition.onerror = (event) => {
    onError(`Voice error: ${event.error}`);
  };

  recognition.onend = () => {
    if (onEnd) onEnd();
  };

  recognition.start();
  return recognition;
}
