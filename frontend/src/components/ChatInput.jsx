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
      darkMode ? 'bg-zinc-950' : 'bg-zinc-50'
    }`}>
      {/* Unified Gemini-Style Rounded Composer Card */}
      <form
        onSubmit={handleSubmit}
        className={`rounded-3xl border px-4 pt-3 pb-2.5 shadow-lg transition-all duration-150 ${
          darkMode
            ? 'bg-[#1e1f22] border-white/10 focus-within:border-white/20'
            : 'bg-white border-zinc-200 focus-within:border-zinc-300'
        }`}
      >
        {/* Top Row: Active Document Chip inside Composer */}
        {effectiveDocs.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 pb-2">
            {effectiveDocs.map((doc, idx) => {
              const docName = doc.name || doc.filename || 'report.pdf';
              const displayName = docName.replace(/\.pdf$/i, '');
              return (
                <div
                  key={doc.id || idx}
                  className={`rounded-xl px-3 py-1.5 text-xs font-medium flex items-center gap-2 w-fit border transition-colors ${
                    darkMode
                      ? 'bg-zinc-800/90 border-white/10 text-zinc-200'
                      : 'bg-zinc-100 border-zinc-200 text-zinc-800'
                  }`}
                >
                  <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold tracking-wider uppercase ${
                    darkMode ? 'bg-red-500/20 text-red-400' : 'bg-red-100 text-red-600'
                  }`}>
                    PDF
                  </span>
                  <span className="max-w-[140px] sm:max-w-[220px] truncate">{displayName}</span>
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
                    className={`p-0.5 rounded-full transition-colors ${
                      darkMode ? 'hover:bg-white/10 text-zinc-400 hover:text-white' : 'hover:bg-zinc-200 text-zinc-500 hover:text-zinc-900'
                    }`}
                  >
                    <X className="w-3.5 h-3.5" />
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
          className={`w-full bg-transparent text-base md:text-sm placeholder-zinc-500 focus:outline-none resize-none leading-relaxed py-1 ${
            darkMode
              ? 'text-white placeholder-zinc-500'
              : 'text-zinc-900 placeholder-zinc-400'
          }`}
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
            className={`p-2 rounded-full transition-colors active:scale-95 ${
              darkMode
                ? 'text-zinc-400 hover:text-white hover:bg-white/5'
                : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100'
            }`}
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
                    ? 'bg-white text-black hover:bg-zinc-200'
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
                className="w-9 h-9 rounded-full bg-blue-600 hover:bg-blue-500 text-white flex items-center justify-center disabled:opacity-40 transition-all active:scale-95 shadow-sm shrink-0"
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
