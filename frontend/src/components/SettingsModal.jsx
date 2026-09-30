import React from 'react';
import { X, Moon, Sun, Shield, Trash2, Cpu } from 'lucide-react';

export default function SettingsModal({
  isOpen,
  onClose,
  darkMode,
  setDarkMode,
  onClearAllChats,
  showToast,
}) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/40 dark:bg-black/60 backdrop-blur-sm animate-fade-in">
      <div className="bg-white dark:bg-zinc-900 border border-zinc-200 dark:border-zinc-800 rounded-2xl shadow-2xl max-w-md w-full overflow-hidden">
        <div className="flex items-center justify-between p-4 px-6 border-b border-zinc-200 dark:border-zinc-800">
          <h3 className="font-semibold text-zinc-900 dark:text-zinc-100 text-base">Settings & Preferences</h3>
          <button
            onClick={onClose}
            className="p-1.5 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-200 rounded-lg hover:bg-zinc-100 dark:hover:bg-zinc-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-6 space-y-5 text-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-200 rounded-xl">
                {darkMode ? <Moon className="w-4 h-4 text-zinc-400" /> : <Sun className="w-4 h-4 text-zinc-500" />}
              </div>
              <div>
                <h4 className="font-medium text-zinc-900 dark:text-zinc-100">Appearance</h4>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">
                  {darkMode ? 'Dark mode active' : 'Light mode active'} • Switch themes
                </p>
              </div>
            </div>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`w-11 h-6 flex items-center rounded-full p-1 transition-colors duration-150 ${
                darkMode ? 'bg-zinc-700 justify-end' : 'bg-zinc-300 justify-start'
              }`}
            >
              <span className={`w-4 h-4 rounded-full shadow-sm transform transition-transform ${
                darkMode ? 'bg-zinc-100' : 'bg-white'
              }`} />
            </button>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded-xl">
                <Cpu className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-medium text-zinc-900 dark:text-zinc-100">RAG Engine</h4>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Google Gemini Flash + FAISS Vector DB</p>
              </div>
            </div>
            <span className="text-[10px] font-medium px-2 py-0.5 bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded border border-zinc-200 dark:border-zinc-700">
              Active
            </span>
          </div>

          <div className="flex items-center justify-between pt-4 border-t border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-3">
              <div className="p-2 bg-zinc-100 dark:bg-zinc-800 text-zinc-700 dark:text-zinc-300 rounded-xl">
                <Trash2 className="w-4 h-4" />
              </div>
              <div>
                <h4 className="font-medium text-zinc-900 dark:text-zinc-100">Clear Conversations</h4>
                <p className="text-xs text-zinc-500 dark:text-zinc-400">Delete all local chat history & vector stores</p>
              </div>
            </div>
            <button
              onClick={() => {
                onClearAllChats();
                onClose();
                if (showToast) showToast('info', 'All conversations cleared');
              }}
              className="px-3 py-1.5 text-xs font-medium text-zinc-700 dark:text-zinc-300 hover:bg-zinc-100 dark:hover:bg-zinc-800 rounded-xl transition-colors border border-zinc-200 dark:border-zinc-700"
            >
              Clear
            </button>
          </div>

          <div className="p-3.5 bg-zinc-50 dark:bg-zinc-950 border border-zinc-200 dark:border-zinc-800 rounded-xl text-xs text-zinc-500 dark:text-zinc-400 flex items-start gap-2.5">
            <Shield className="w-4 h-4 text-zinc-500 shrink-0 mt-0.5" />
            <div>
              <strong className="text-zinc-900 dark:text-zinc-200 font-medium block mb-0.5">Privacy & Compliance</strong>
              MediSkye does not retain medical diagnostic data across server restarts. PDF reports are embedded transiently per session ID.
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-zinc-100 dark:border-zinc-800 bg-zinc-50 dark:bg-zinc-950 text-right">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-zinc-900 dark:bg-zinc-100 text-white dark:text-zinc-900 font-medium rounded-xl text-xs"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
