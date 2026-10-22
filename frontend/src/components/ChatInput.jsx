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
  showToast,
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
    if (!text.trim() || isSubmittingRef.current || isGenerating || disabled) return;
    isSubmittingRef.current = true;
    onSendMessage(text.trim());
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
      if (showToast) showToast('info', t('chat.listening', 'Listening...'), t('chat.speak_question', 'Speak your medical question'));
      recognitionRef.current = startSpeechRecognition(
        (transcript) => {
          setText(transcript);
        },
        (error) => {
          if (showToast) showToast('error', error);
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

  // Derive active documents to show inside composer card
  const effectiveDocs = attachedDocuments && attachedDocuments.length > 0
    ? attachedDocuments
    : (activeFile ? [activeFile] : []);

  return (
    <div className={`w-full max-w-3xl mx-auto px-4 md:px-6 pb-3 transition-colors duration-200 ${
      darkMode ? 'bg-[#07090e]' : 'bg-zinc-50'
    }`}>
      {/* Unified Gemini-Style Rounded Composer Card */}
      <form
        onSubmit={handleSubmit}
        className="rounded-[28px] bg-[#151a23] border border-white/[0.08] focus-within:border-cyan-500/35 px-4 pt-3.5 pb-2.5 shadow-xl transition-all duration-150"
      >
        {/* Top Row: Active Document Chip inside Composer */}
        {effectiveDocs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            {effectiveDocs.map((doc, idx) => {
              const docName = doc.name || doc.filename || 'report.pdf';
              const displayName = docName.replace(/\.pdf$/i, '');
              return (
                <div
                  key={doc.id || idx}
                  className="inline-flex items-center gap-2.5 rounded-2xl bg-[#252b36] px-3.5 py-2 text-xs text-slate-100 mb-2 max-w-full"
                >
                  <span className="font-semibold text-slate-300 shrink-0">
                    PDF
                  </span>
                  <span className="truncate max-w-[180px] sm:max-w-[260px] text-slate-100">{displayName}</span>
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

        {/* Middle Row: Auto-expanding Textarea */}
        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t('chat.input_placeholder', 'Ask MediSkye...')}
          rows={1}
          className="text-base md:text-sm text-slate-100 placeholder-slate-500 bg-transparent border-0 focus:ring-0 focus:outline-none w-full resize-none leading-relaxed py-1"
        />

        {/* Bottom Action Row */}
        <div className="flex items-center justify-between pt-2">
          {/* Bottom Left: '+' File Upload Button */}
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
            className="w-9 h-9 -ml-1 rounded-full text-slate-300 hover:text-white hover:bg-white/[0.06] flex items-center justify-center transition active:scale-95"
          >
            <Plus className="w-5 h-5" />
          </button>

          {/* Bottom Right: Voice + Circular Accent Send Button */}
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={toggleVoiceInput}
              title={isListening ? t('chat.stop_listening', 'Stop listening') : t('chat.voice_input', 'Voice input')}
              aria-label={isListening ? t('chat.stop_listening', 'Stop listening') : t('chat.voice_input', 'Voice input')}
              className={`p-2 rounded-full transition-colors active:scale-95 ${
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
                className={`w-9 h-9 rounded-full flex items-center justify-center transition-all active:scale-95 shadow-xs ${
                  darkMode
                    ? 'bg-cyan-500 hover:bg-cyan-400 text-slate-950'
                    : 'bg-zinc-900 text-white hover:bg-zinc-800'
                }`}
              >
                <Square className="w-4 h-4 fill-current" />
              </button>
            ) : (
              <button
                type="submit"
                onClick={handleSubmit}
                disabled={!text.trim() || disabled}
                title={t('chat.send_message', 'Send message')}
                aria-label={t('chat.send_message', 'Send message')}
                className="w-9 h-9 rounded-full bg-cyan-500 hover:bg-cyan-400 text-slate-950 flex items-center justify-center disabled:opacity-40 transition-all active:scale-95 shadow-sm shrink-0"
              >
                <ArrowUp className="w-4 h-4 stroke-[2.5]" />
              </button>
            )}
          </div>
        </div>
      </form>

      {/* Micro-Disclaimer */}
      <div className={`mt-2 text-center text-[11px] truncate ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
        {t('chat.disclaimer', 'MediSkye AI can make mistakes. Always verify critical results with a qualified healthcare professional.')}
      </div>
    </div>
  );
});

export default ChatInput;
