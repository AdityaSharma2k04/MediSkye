import React, { useRef, useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import { Paperclip, ArrowUp, Mic, MicOff, Square, X, FileText } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { startSpeechRecognition } from '../services/speech';
import { cn } from '../lib/cn';
import { stripOuterQuotes } from '../lib/clinical';

export function isTouchOrMobileDevice() {
  if (typeof window === 'undefined') return false;
  return Boolean(
    window.matchMedia?.('(pointer: coarse)')?.matches ||
    'ontouchstart' in window ||
    (navigator?.maxTouchPoints && navigator.maxTouchPoints > 0) ||
    (typeof window.innerWidth === 'number' && window.innerWidth < 1024)
  );
}

const ChatInput = forwardRef(
  (
    {
      onSendMessage,
      onAttachFile,
      activeFile,
      attachedDocuments = [],
      onDetachDocument,
      onRemoveFile,
      isGenerating,
      onStopGeneration,
      disabled = false,
      hidden = false,
      showKeyboardHint = false,
    },
    ref
  ) => {
    const { t } = useTranslation();
    const [text, setText] = useState('');
    const [isListening, setIsListening] = useState(false);
    const [isTouch, setIsTouch] = useState(() => isTouchOrMobileDevice());
    const recognitionRef = useRef(null);
    const textareaRef = useRef(null);
    const fileInputRef = useRef(null);
    const isSubmittingRef = useRef(false);

    useEffect(() => {
      setIsTouch(isTouchOrMobileDevice());
      const onResize = () => setIsTouch(isTouchOrMobileDevice());
      window.addEventListener?.('resize', onResize);
      return () => window.removeEventListener?.('resize', onResize);
    }, []);

    // Stop speech recognition on unmount (no background listening)
    useEffect(() => {
      return () => {
        if (recognitionRef.current) {
          try {
            recognitionRef.current.stop();
          } catch (e) {
            /* already stopped */
          }
        }
      };
    }, []);

    useImperativeHandle(ref, () => ({
      openFileUpload: () => {
        if (fileInputRef.current) fileInputRef.current.click();
      },
      focus: () => textareaRef.current?.focus(),
      insertText: (value) => {
        setText(value);
        requestAnimationFrame(() => {
          const el = textareaRef.current;
          if (el) {
            el.focus();
            el.setSelectionRange(value.length, value.length);
          }
        });
      },
    }));

    useEffect(() => {
      if (textareaRef.current) {
        textareaRef.current.style.height = 'auto';
        textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 200)}px`;
      }
    }, [text]);

    const handleSubmit = (e) => {
      if (e) e.preventDefault();
      const trimmed = text.trim();
      if (!trimmed || isSubmittingRef.current || isGenerating || disabled) return;

      // Strip outer quotation marks if the user pasted a quoted question
      const cleanText = stripOuterQuotes(trimmed);
      if (!cleanText) return;

      isSubmittingRef.current = true;
      onSendMessage(cleanText);
      setText('');
      if (textareaRef.current) textareaRef.current.style.height = 'auto';
      setTimeout(() => {
        isSubmittingRef.current = false;
      }, 300);
    };

    const handleKeyDown = (e) => {
      if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent?.isComposing) {
        if (isTouchOrMobileDevice()) {
          // On touch/mobile devices, Enter inserts a newline (\n) rather than submitting
          return;
        }
        e.preventDefault();
        handleSubmit();
      }
    };

    const toggleVoiceInput = () => {
      if (isListening) {
        if (recognitionRef.current) recognitionRef.current.stop();
        setIsListening(false);
      } else {
        setIsListening(true);
        recognitionRef.current = startSpeechRecognition(
          (transcript) => setText(transcript),
          (error) => {
            console.error('Speech recognition error:', error);
            setIsListening(false);
          },
          () => setIsListening(false)
        );
      }
    };

    const handleFileChange = (e) => {
      if (e.target.files && e.target.files.length > 0) {
        const file = e.target.files[0];
        onAttachFile(file);
      }
      // Allow re-selecting the same file
      try {
        e.target.value = '';
      } catch {
        /* read-only in some browsers */
      }
    };

    const effectiveDocs = attachedDocuments || [];
    const canSend = Boolean(text.trim()) && !disabled;

    return (
      <div className={cn('w-full max-w-3xl mx-auto px-3 sm:px-6 pt-1 pb-safe-composer', hidden && 'hidden')}>
        <form
          onSubmit={handleSubmit}
          className={cn(
            'relative rounded-[24px] bg-graphite/95 border border-white/[0.09] shadow-[0_12px_40px_-16px_rgba(0,0,0,0.8)] shadow-specular',
            'focus-within:border-cyan-500/40 focus-within:shadow-glow transition-[border-color,box-shadow] duration-200',
            'backdrop-blur-xl'
          )}
        >
          {effectiveDocs.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 px-3 pt-3">
              {effectiveDocs.map((doc, idx) => {
                const docName = doc.name || doc.filename || 'report.pdf';
                const displayName = docName.replace(/\.pdf$/i, '');
                return (
                  <div
                    key={doc.id || idx}
                    className="inline-flex items-center gap-2 rounded-xl bg-white/[0.05] border border-white/[0.08] pl-2 pr-1 h-8 text-xs text-ink max-w-full"
                  >
                    <FileText className="w-3.5 h-3.5 text-cyan-300 shrink-0" />
                    <span className="truncate max-w-[160px] sm:max-w-[260px]">{displayName}</span>
                    <button
                      type="button"
                      onClick={() => {
                        if (onDetachDocument && doc.id) onDetachDocument(doc.id);
                        else if (onRemoveFile) onRemoveFile();
                      }}
                      aria-label={`Detach ${docName}`}
                      title={`Detach ${docName}`}
                      className="w-6 h-6 rounded-lg text-ink-mute hover:text-white hover:bg-white/[0.08] flex items-center justify-center shrink-0 transition"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          <div className="flex items-end gap-1 px-2 py-2">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileChange}
              accept=".pdf,.jpg,.jpeg,.png"
              className="hidden"
              tabIndex={-1}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              title={t('chat.upload_title', 'Upload medical report (PDF, JPG, PNG · up to 50MB)')}
              aria-label="Upload report"
              className="ms-tap w-10 h-10 rounded-full text-ink-mute hover:text-white hover:bg-white/[0.06] flex items-center justify-center transition shrink-0 active:scale-95"
            >
              <Paperclip className="w-[18px] h-[18px]" />
            </button>

            <textarea
              ref={textareaRef}
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={activeFile ? t('chat.input_placeholder_report', 'Ask about this report...') : t('chat.input_placeholder', 'Ask MediSkye...')}
              rows={1}
              enterKeyHint={isTouch ? 'enter' : 'send'}
              className="ms-composer-input flex-1 min-w-0 self-center text-base sm:text-[15px] text-white placeholder:text-ink-faint bg-transparent border-0 focus:ring-0 focus:outline-none resize-none leading-6 py-2 max-h-[200px]"
            />

            <div className="flex items-center gap-1 shrink-0">
              <button
                type="button"
                onClick={toggleVoiceInput}
                title={isListening ? t('chat.stop_listening', 'Stop listening') : t('chat.voice_input', 'Voice input')}
                aria-label={isListening ? t('chat.stop_listening', 'Stop listening') : t('chat.voice_input', 'Voice input')}
                aria-pressed={isListening}
                className={cn(
                  'ms-tap w-10 h-10 rounded-full flex items-center justify-center transition-colors active:scale-95',
                  isListening ? 'text-rose-200 bg-rose-500/15 animate-pulse' : 'text-ink-mute hover:text-white hover:bg-white/[0.06]'
                )}
              >
                {isListening ? <MicOff className="w-[18px] h-[18px]" /> : <Mic className="w-[18px] h-[18px]" />}
              </button>

              {isGenerating ? (
                <button
                  type="button"
                  onClick={onStopGeneration}
                  title={t('chat.stop_generation', 'Stop generation')}
                  aria-label={t('chat.stop_generation', 'Stop generation')}
                  className="ms-tap w-10 h-10 rounded-full flex items-center justify-center transition-all active:scale-95 bg-white text-slate-950 hover:bg-cyan-100"
                >
                  <Square className="w-3.5 h-3.5 fill-current" />
                </button>
              ) : (
                <button
                  type="submit"
                  onClick={handleSubmit}
                  disabled={!text.trim() || disabled}
                  title={t('chat.send_message', 'Send message')}
                  aria-label={t('chat.send_message', 'Send message')}
                  className={cn(
                    'ms-tap w-10 h-10 rounded-full flex items-center justify-center transition-all active:scale-95 shrink-0',
                    canSend ? 'bg-clinical-cyan text-slate-950 hover:bg-cyan-300 shadow-[0_6px_20px_-6px_rgba(6,182,212,0.8)]' : 'bg-white/[0.06] text-ink-faint',
                    'disabled:cursor-not-allowed'
                  )}
                >
                  <ArrowUp className="w-[18px] h-[18px] stroke-[2.5]" />
                </button>
              )}
            </div>
          </div>
        </form>

        <div className="mt-1.5 flex items-center justify-center gap-3 text-[11px] leading-tight text-ink-faint px-2 text-center">
          <span>{t('chat.disclaimer', 'MediSkye AI can make mistakes. Always verify critical results with a qualified healthcare professional.')}</span>
          {showKeyboardHint && (
            <span className="hidden xl:inline whitespace-nowrap text-ink-faint/80">
              <span className="ms-num">Shift+Enter</span> for a new line
            </span>
          )}
        </div>
      </div>
    );
  }
);

export default ChatInput;
