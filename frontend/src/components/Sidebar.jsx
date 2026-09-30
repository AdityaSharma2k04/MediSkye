import React, { useState } from 'react';
import {
  Plus,
  Search,
  MessageSquare,
  FileText,
  Settings,
  Sun,
  Moon,
  ChevronLeft,
  ChevronRight,
  Shield,
  Activity,
  Globe,
  LogOut,
  User,
  Trash2,
} from 'lucide-react';

export default function Sidebar({
  isOpen,
  onToggle,
  conversations,
  activeSessionId,
  onSelectChat,
  onNewChat,
  onOpenSettings,
  onOpenProfile,
  darkMode,
  setDarkMode,
  activePdf,
  language,
  setLanguage,
  onLogout,
  onDeleteChat,
  currentUser,
}) {

  const [searchQuery, setSearchQuery] = useState('');

  const filteredChats = conversations.filter((c) =>
    c.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const languages = [
    { code: 'English', label: 'English (US)' },
    { code: 'Spanish', label: 'Español' },
    { code: 'Hindi', label: 'हिन्दी' },
    { code: 'French', label: 'Français' },
    { code: 'German', label: 'Deutsch' },
  ];

  return (
    <aside
      className={`fixed lg:static inset-y-0 left-0 z-40 flex flex-col transition-all duration-300 ease-in-out border-r ${
        darkMode
          ? 'bg-[#09090B] border-zinc-800/80'
          : 'bg-white border-zinc-200'
      } ${isOpen ? 'w-64 sm:w-72' : 'w-0 lg:w-16 overflow-hidden'}`}
    >
      <div className={`p-4 flex items-center justify-between border-b ${
        darkMode ? 'border-zinc-800/80' : 'border-zinc-200'
      }`}>
        {isOpen ? (
          <div className="flex items-center gap-2.5">
            <div className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs ${
              darkMode ? 'bg-zinc-100 text-black' : 'bg-zinc-900 text-white'
            }`}>
              <Activity className="w-3.5 h-3.5" />
            </div>
            <div>
              <h1 className={`font-semibold text-sm tracking-tight ${
                darkMode ? 'text-white' : 'text-zinc-900'
              }`}>MediSkye AI</h1>
              <span className={`text-[10px] font-medium uppercase tracking-wider block ${
                darkMode ? 'text-zinc-400' : 'text-zinc-500'
              }`}>
                Medical RAG
              </span>
            </div>
          </div>
        ) : (
          <div className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs mx-auto ${
            darkMode ? 'bg-zinc-100 text-black' : 'bg-zinc-900 text-white'
          }`}>
            M
          </div>
        )}

        <button
          onClick={onToggle}
          className={`p-1.5 rounded-lg transition-colors ${
            darkMode
              ? 'text-zinc-400 hover:text-white hover:bg-zinc-800'
              : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100'
          }`}
          title={isOpen ? 'Collapse Sidebar' : 'Expand Sidebar'}
        >
          {isOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {isOpen && (
        <div className="flex-1 flex flex-col overflow-hidden p-3 space-y-3">
          <button
            onClick={onNewChat}
            className={`w-full flex items-center justify-center gap-2 py-2 px-3.5 rounded-xl font-medium text-xs transition-all duration-150 ${
              darkMode
                ? 'bg-zinc-100 hover:bg-zinc-200 text-black'
                : 'bg-zinc-900 hover:bg-zinc-800 text-white'
            }`}
          >
            <Plus className="w-3.5 h-3.5" />
            <span>New Consultation</span>
          </button>

          {activePdf && (
            <div className={`p-2.5 rounded-xl text-xs flex items-center gap-2.5 border ${
              darkMode
                ? 'bg-zinc-900 border-zinc-800'
                : 'bg-zinc-50 border-zinc-200'
            }`}>
              <FileText className={`w-4 h-4 shrink-0 ${darkMode ? 'text-zinc-300' : 'text-zinc-500'}`} />
              <div className="overflow-hidden">
                <div className={`font-medium truncate ${darkMode ? 'text-white' : 'text-zinc-900'}`}>{activePdf.name}</div>
                <div className={`text-[10px] ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>Indexed Medical PDF (50MB Max)</div>
              </div>
            </div>
          )}

          <div className={`relative flex items-center gap-2 px-2.5 py-1.5 rounded-xl text-xs border ${
            darkMode
              ? 'bg-zinc-900/90 border-zinc-800 text-zinc-300'
              : 'bg-zinc-50 border-zinc-200 text-zinc-700'
          }`}>
            <Globe className={`w-3.5 h-3.5 shrink-0 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
            <select
              value={language || 'English'}
              onChange={(e) => setLanguage && setLanguage(e.target.value)}
              className={`bg-transparent text-xs w-full focus:outline-none cursor-pointer ${
                darkMode ? 'text-white' : 'text-zinc-900'
              }`}
            >
              {languages.map((lang) => (
                <option key={lang.code} value={lang.code} className={darkMode ? 'bg-zinc-900 text-white' : 'bg-white text-zinc-900'}>
                  {lang.label}
                </option>
              ))}
            </select>
          </div>

          <div className="relative">
            <Search className={`w-3.5 h-3.5 absolute left-3 top-2.5 ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`} />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search chats..."
              className={`w-full pl-8 pr-3 py-1.5 text-xs rounded-xl border focus:outline-none transition-all ${
                darkMode
                  ? 'bg-zinc-900/60 text-white placeholder-zinc-500 border-zinc-800 focus:border-zinc-700'
                  : 'bg-zinc-50 text-zinc-900 placeholder-zinc-400 border-zinc-200 focus:border-zinc-400'
              }`}
            />
          </div>

          <div className="flex-1 overflow-y-auto space-y-1 pr-1">
            <div className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-1 ${
              darkMode ? 'text-zinc-500' : 'text-zinc-400'
            }`}>
              History
            </div>

            {filteredChats.length === 0 ? (
              <div className={`text-center py-6 text-xs ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>No chats found</div>
            ) : (
              filteredChats.map((chat) => {
                const isActive = chat.id === activeSessionId;
                return (
                  <div key={chat.id} className="relative group flex items-center w-full">
                    <button
                      onClick={() => onSelectChat(chat.id)}
                      className={`flex-1 text-left p-2 pr-8 rounded-xl text-xs flex items-center gap-2.5 transition-colors ${
                        isActive
                          ? darkMode
                            ? 'bg-zinc-800 text-white font-medium border border-zinc-700'
                            : 'bg-zinc-100 text-zinc-900 font-medium border border-zinc-300'
                          : darkMode
                            ? 'text-zinc-400 hover:bg-zinc-900/50 hover:text-white'
                            : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900'
                      }`}
                    >
                      <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-60" />
                      <span className="truncate flex-1">{chat.title || 'Medical Consultation'}</span>
                    </button>
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (onDeleteChat) onDeleteChat(chat.id);
                      }}
                      className={`absolute right-1.5 p-1 rounded transition-all opacity-0 group-hover:opacity-100 ${
                        darkMode
                          ? 'text-zinc-500 hover:text-red-400 hover:bg-zinc-700'
                          : 'text-zinc-400 hover:text-red-500 hover:bg-zinc-100'
                      }`}
                      title="Delete chat"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                );
              })
            )}
          </div>

          <div className={`pt-3 border-t space-y-1 ${darkMode ? 'border-zinc-800' : 'border-zinc-200'}`}>
            <button
              onClick={() => setDarkMode(!darkMode)}
              className={`w-full flex items-center justify-between p-2 rounded-xl text-xs transition-colors ${
                darkMode
                  ? 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
                  : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900'
              }`}
            >
              <div className="flex items-center gap-2">
                {darkMode ? <Moon className="w-3.5 h-3.5" /> : <Sun className="w-3.5 h-3.5" />}
                <span>{darkMode ? 'Dark Theme' : 'Light Theme'}</span>
              </div>
              <span className={`text-[10px] ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                {darkMode ? 'Obsidian' : 'Clean'}
              </span>
            </button>

            <button
              onClick={onOpenProfile}
              className={`w-full flex items-center justify-between p-2 rounded-xl text-xs transition-colors ${
                darkMode
                  ? 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
                  : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900'
              }`}
            >
              <div className="flex items-center gap-2">
                <User className="w-3.5 h-3.5 text-indigo-400" />
                <span>Profile & Caregiver Hub</span>
              </div>
            </button>

            <button
              onClick={onOpenSettings}
              className={`w-full flex items-center gap-2 p-2 rounded-xl text-xs transition-colors ${
                darkMode
                  ? 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
                  : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900'
              }`}
            >
              <Settings className="w-3.5 h-3.5" />
              <span>Settings</span>
            </button>

            <button
              onClick={onLogout}
              className="w-full flex items-center gap-2 p-2 rounded-xl text-xs text-red-400 hover:bg-red-900/50 hover:text-red-300 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5 text-red-400" />
              <span>Logout</span>
            </button>

            <div className="pt-2 flex items-center gap-2.5 px-2">
              <div className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${
                darkMode ? 'bg-zinc-800 text-zinc-300' : 'bg-zinc-100 text-zinc-600'
              }`}>
                <Shield className={`w-3 h-3 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
              </div>
              <div className="overflow-hidden text-[11px]">
                <div className={`font-medium truncate ${darkMode ? 'text-white' : 'text-zinc-900'}`}>
                  {currentUser?.full_name || (currentUser?.email ? currentUser.email.split('@')[0] : 'Patient Session')}
                </div>
                <div className={`text-[10px] truncate ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                  {currentUser?.email || 'HIPAA Encrypted'}
                </div>
              </div>
            </div>

          </div>
        </div>
      )}
    </aside>
  );
}
