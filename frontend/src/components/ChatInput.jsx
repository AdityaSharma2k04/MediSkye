import React, { useRef, useState, useEffect, forwardRef, useImperativeHandle } from 'react';
import { Plus, ArrowUp, Mic, MicOff, Square, X } from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { startSpeechRecognition } from '../services/speech';

const ChatInput = forwardRef(({
  onSendMessage,
  onAttachFile,
  activeFile,
  attachedDocuments = [],
  onDetachDocument,
  onRemoveFile,
  isGenerating,
  onStopGeneration,
  darkMode,
  disabled = false,
}, ref) => {
  const { t } = useTranslation();
  const [text, setText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);
  const isSubmittingRef = useRef(false);

  // Clean up speech recognition on unmount to prevent memory leaks / background listening
  useEffect(() => {
    return () => {
      if (recognitionRef.current) {
        try {
          recognitionRef.current.stop();
        } catch (e) {}
      }
    };
  }, []);

  useImperativeHandle(ref, () => ({
    openFileUpload: () => {
      if (fileInputRef.current) {
        fileInputRef.current.click();
      }
    }
  }));

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    let trimmed = text.trim();
    if (!trimmed || isSubmittingRef.current || isGenerating || disabled) return;

    // Strip leading and trailing outer quotation marks if the user pasted wrapped in quotes
    let cleanText = trimmed.replace(/^["'“”‘’]+|["'“”‘’]+$/g, '').trim();
    if (!cleanText) return;

    isSubmittingRef.current = true;
    onSendMessage(cleanText);
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
    setTimeout(() => {
      isSubmittingRef.current = false;
    }, 300);
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
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
        (transcript) => {
          setText(transcript);
        },
        (error) => {
          console.error('Speech recognition error:', error);
          setIsListening(false);
        },
        () => {
          setIsListening(false);
        }
      );
    }
  };

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      const file = e.target.files[0];
      onAttachFile(file);
    }
  };

  // Active staged documents to show inside composer card
  const effectiveDocs = attachedDocuments || [];

  return (
    <div className={`w-full max-w-3xl mx-auto px-4 md:px-6 pb-2 transition-colors duration-200 ${
      darkMode ? 'bg-[#07090e]' : 'bg-zinc-50'
    }`}>
      {/* Unified Gemini-Style Compact Composer Card */}
      <form
        onSubmit={handleSubmit}
        className="rounded-[26px] bg-[#151a23] border border-white/[0.08] focus-within:border-cyan-500/35 px-3 py-1.5 sm:px-4 sm:py-2 shadow-lg transition-all duration-150"
      >
        {/* If a new attachment is actively staged, show it compactly above */}
        {effectiveDocs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pb-2 mb-1.5 border-b border-white/[0.06]">
            {effectiveDocs.map((doc, idx) => {
              const docName = doc.name || doc.filename || 'report.pdf';
              const displayName = docName.replace(/\.pdf$/i, '');
              return (
                <div
                  key={doc.id || idx}
                  className="inline-flex items-center gap-2 rounded-xl bg-[#252b36] px-2.5 py-1 text-xs text-slate-100 max-w-full"
                >
                  <span className="font-semibold text-slate-300 shrink-0 text-[11px]">
                    PDF
                  </span>
                  <span className="truncate max-w-[160px] sm:max-w-[240px] text-slate-100 text-xs">{displayName}</span>
                  <button
                    type="button"
                    onClick={() => {
                      if (onDetachDocument && doc.id) {
                        onDetachDocument(doc.id);
                      } else if (onRemoveFile) {
                        onRemoveFile();
                      }
                    }}
                    aria-label={`Detach ${docName}`}
                    title={`Detach ${docName}`}
                    className="w-4 h-4 rounded-full bg-slate-200 hover:bg-white text-slate-900 flex items-center justify-center shrink-0 transition"
                  >
                    <X className="w-3 h-3 stroke-[2.5]" />
                  </button>
                </div>
              );
            })}
          </div>
        )}

        <div className="flex items-center gap-1.5 sm:gap-2">
          {/* Left: '+' File Upload Button */}
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileChange}
            accept=".pdf,.jpg,.jpeg,.png"
            className="hidden"
          />
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            title={t('chat.upload_title', 'Upload medical report (PDF, JPG, PNG · up to 50MB)')}
            aria-label="Upload report"
            className="w-8 h-8 rounded-full text-slate-400 hover:text-white hover:bg-white/[0.06] flex items-center justify-center transition shrink-0 active:scale-95"
          >
            <Plus className="w-4 h-4 sm:w-5 sm:h-5" />
          </button>

          {/* Center: Auto-expanding Textarea */}
          <textarea
            ref={textareaRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={activeFile ? t('chat.input_placeholder_report', 'Ask about this report...') : t('chat.input_placeholder', 'Ask MediSkye...')}
            rows={1}
            className="flex-1 min-w-0 text-[15px] sm:text-sm text-slate-100 placeholder-slate-400 bg-transparent border-0 focus:ring-0 focus:outline-none resize-none leading-normal py-1 max-h-32"
          />

          {/* Right: Voice + Circular Accent Send Button */}
          <div className="flex items-center gap-1 shrink-0">
            <button
              type="button"
              onClick={toggleVoiceInput}
              title={isListening ? t('chat.stop_listening', 'Stop listening') : t('chat.voice_input', 'Voice input')}
              aria-label={isListening ? t('chat.stop_listening', 'Stop listening') : t('chat.voice_input', 'Voice input')}
              className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors active:scale-95 ${
                isListening
                  ? darkMode
                    ? 'text-white bg-zinc-800 animate-pulse'
                    : 'text-zinc-900 bg-zinc-200 animate-pulse'
                  : darkMode
                    ? 'text-zinc-400 hover:text-white hover:bg-white/5'
                    : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100'
              }`}
            >
              {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
            </button>

            {isGenerating ? (
              <button
                type="button"
                onClick={onStopGeneration}
                title={t('chat.stop_generation', 'Stop generation')}
                aria-label={t('chat.stop_generation', 'Stop generation')}
                className={`w-8 h-8 rounded-full flex items-center justify-center transition-all active:scale-95 shadow-xs ${
                  darkMode
                    ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950'
                    : 'bg-zinc-900 text-white hover:bg-zinc-800'
                }`}
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
                className="w-8 h-8 rounded-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 flex items-center justify-center disabled:opacity-30 transition-all active:scale-95 shadow-xs shrink-0"
              >
                <ArrowUp className="w-4 h-4 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>
      </form>

      {/* Micro-Disclaimer */}
      <div className={`mt-1.5 text-center text-[11px] leading-tight max-w-xl mx-auto px-2 ${darkMode ? 'text-slate-400' : 'text-zinc-500'}`}>
        {t('chat.disclaimer', 'MediSkye AI can make mistakes. Always verify critical results with a qualified healthcare professional.')}
      </div>
    </div>
  );
});

export default ChatInput;
