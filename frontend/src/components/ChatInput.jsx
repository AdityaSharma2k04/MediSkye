import React, { useRef, useState, useEffect } from 'react';
import { Paperclip, Mic, MicOff, Send, Square, FileText, X } from 'lucide-react';
import { startSpeechRecognition } from '../services/speech';
import PatientContextSelector from './PatientContextSelector';

export default function ChatInput({
  onSendMessage,
  onAttachFile,
  activeFile,
  onRemoveFile,
  isGenerating,
  onStopGeneration,
  showToast,
  darkMode,
  currentUser,
  dependents,
  selectedPatientId,
  onSelectPatient,
  onOpenDependents,
}) {
  const [text, setText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const recognitionRef = useRef(null);
  const textareaRef = useRef(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 160)}px`;
    }
  }, [text]);

  const handleSubmit = (e) => {
    if (e) e.preventDefault();
    if (!text.trim() || isGenerating) return;
    onSendMessage(text.trim());
    setText('');
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
    }
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
      if (showToast) showToast('info', 'Listening...', 'Speak your medical question');
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

  return (
    <div className={`max-w-3xl w-full mx-auto px-4 pb-4 sm:pb-6 transition-colors duration-200 ${
      darkMode ? 'bg-black' : 'bg-zinc-50'
    }`}>
      {/* Context Selector Header Bar */}
      <div className="mb-2 flex items-center justify-between">
        <PatientContextSelector
          currentUser={currentUser}
          dependents={dependents}
          selectedPatientId={selectedPatientId}
          onSelectPatient={onSelectPatient}
          onOpenDependents={onOpenDependents}
          darkMode={darkMode}
        />
      </div>

      {activeFile && (
        <div className={`mb-2 flex items-center justify-between gap-2 px-3 py-1.5 rounded-xl text-xs animate-slide-in border ${
          darkMode
            ? 'bg-zinc-900 border-zinc-800 text-white'
            : 'bg-zinc-100 border-zinc-200 text-zinc-900'
        }`}>
          <div className="flex items-center gap-2 truncate">
            <FileText className={`w-4 h-4 shrink-0 ${darkMode ? 'text-zinc-300' : 'text-zinc-500'}`} />
            <span className="font-medium truncate">{activeFile.name}</span>
            <span className={`text-[10px] ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>({(activeFile.size / (1024 * 1024)).toFixed(2)} MB)</span>
          </div>
          <button
            onClick={onRemoveFile}
            className={`p-1 rounded-lg ${darkMode ? 'text-zinc-400 hover:text-white' : 'text-zinc-400 hover:text-zinc-900'}`}
            title="Remove file"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      <form
        onSubmit={handleSubmit}
        className={`relative flex items-end gap-2 p-2 sm:p-2.5 rounded-2xl shadow-sm transition-all duration-150 border ${
          darkMode
            ? 'bg-[#121212] border-zinc-800 focus-within:border-zinc-700 focus-within:ring-2 focus-within:ring-zinc-700/20'
            : 'bg-white border-zinc-200 focus-within:border-zinc-400 focus-within:ring-2 focus-within:ring-zinc-400/20'
        }`}
      >

        <input
          type="file"
          ref={fileInputRef}
          onChange={handleFileChange}
          accept="application/pdf"
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          title="Upload medical PDF report (50MB Max)"
          className={`p-2 rounded-xl transition-colors shrink-0 ${
            darkMode
              ? 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              : 'text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100'
          }`}
        >
          <Paperclip className="w-4 h-4" />
        </button>

        <textarea
          ref={textareaRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask a medical question about your report..."
          rows={1}
          className={`flex-1 bg-transparent text-sm focus:outline-none resize-none py-1.5 max-h-40 ${
            darkMode
              ? 'text-white placeholder-zinc-500'
              : 'text-zinc-900 placeholder-zinc-400'
          }`}
        />

        <button
          type="button"
          onClick={toggleVoiceInput}
          title={isListening ? 'Stop listening' : 'Voice input'}
          className={`p-2 rounded-xl transition-colors shrink-0 ${
            isListening
              ? darkMode
                ? 'text-white bg-zinc-800 animate-pulse'
                : 'text-zinc-900 bg-zinc-200 animate-pulse'
              : darkMode
                ? 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                : 'text-zinc-400 hover:text-zinc-900 hover:bg-zinc-100'
          }`}
        >
          {isListening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}
        </button>

        {isGenerating ? (
          <button
            type="button"
            onClick={onStopGeneration}
            title="Stop generation"
            className={`p-2 rounded-xl transition-opacity shrink-0 ${
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
            disabled={!text.trim()}
            title="Send message"
            className={`p-2 disabled:opacity-30 rounded-xl transition-all shadow-sm shrink-0 font-bold ${
              darkMode
                ? 'bg-white hover:bg-zinc-200 text-black'
                : 'bg-zinc-900 hover:bg-zinc-800 text-white'
            }`}
          >
            <Send className="w-4 h-4" />
          </button>
        )}
      </form>

      <div className={`mt-2 text-center text-[11px] ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
        MediSkye AI can make mistakes. Always verify critical results with a qualified healthcare professional.
      </div>
    </div>
  );
}
