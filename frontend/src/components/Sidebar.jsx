import React, { useState, useRef, useEffect } from 'react';
import {
  Plus,
  Search,
  MessageSquare,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  Shield,
  Activity,
  User,
  Trash2,
  MoreHorizontal,
  Pencil,
  Check,
  X,
  LogOut,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ConfirmModal from './ConfirmModal';

function formatRelativeTime(ts) {
  if (!ts) return '';
  const date = typeof ts === 'string' ? new Date(ts) : ts;
  if (isNaN(date)) return '';
  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  if (days < 7) return `${days}d ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

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
  activePdf,
  onLogout,
  onDeleteChat,
  onRenameChat,
  currentUser,
}) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState('');
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [pendingLogout, setPendingLogout] = useState(false);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);

  // Guarantee menu is closed on every mount (guards against StrictMode double-invoke)
  useEffect(() => { setOpenMenuId(null); }, []);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef(null);
  const menuRefs = useRef({});

  const filteredChats = conversations.filter((c) =>
    (c.title || 'New Conversation').toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Close menu when clicking outside or pressing Escape — only active while a menu is open
  useEffect(() => {
    if (!openMenuId) return;
    const handleMouseDown = (e) => {
      const ref = menuRefs.current[openMenuId];
      if (ref && !ref.contains(e.target)) {
        setOpenMenuId(null);
      }
    };
    const handleKeyDown = (e) => {
      if (e.key === 'Escape') setOpenMenuId(null);
    };
    document.addEventListener('mousedown', handleMouseDown);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleMouseDown);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [openMenuId]);

  // Focus rename input when opened
  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const handleDeleteConfirmed = () => {
    if (pendingDeleteId && onDeleteChat) {
      onDeleteChat(pendingDeleteId, /* skipConfirm */ true);
    }
    setPendingDeleteId(null);
  };

  const startRename = (chat) => {
    setOpenMenuId(null);
    setRenamingId(chat.id);
    setRenameValue(chat.title || 'New Conversation');
  };

  const commitRename = (id) => {
    if (renameValue.trim() && onRenameChat) {
      onRenameChat(id, renameValue.trim());
    }
    setRenamingId(null);
  };

  const cancelRename = () => {
    setRenamingId(null);
    setRenameValue('');
  };

  return (
    <>
      <aside
        className={`w-72 h-full flex flex-col border-r ${
          darkMode
            ? 'bg-[#09090B] border-zinc-800/80'
            : 'bg-white border-zinc-200'
        }`}
      >
        <div className={`p-4 flex items-center justify-between border-b ${darkMode ? 'border-zinc-800/80' : 'border-zinc-200'}`}>
          {isOpen ? (
            <div className="flex items-center gap-2.5">
              <div className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs ${darkMode ? 'bg-zinc-100 text-black' : 'bg-zinc-900 text-white'}`}>
                <Activity className="w-3.5 h-3.5" />
              </div>
              <div>
                <h1 className={`font-semibold text-sm tracking-tight ${darkMode ? 'text-white' : 'text-zinc-900'}`}>{t('sidebar.title', 'MediSkye AI')}</h1>
                <span className={`text-[10px] font-medium uppercase tracking-wider block ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
                  {t('sidebar.medical_assistant', 'Medical Assistant')}
                </span>
              </div>
            </div>
          ) : (
            <div className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs mx-auto ${darkMode ? 'bg-zinc-100 text-black' : 'bg-zinc-900 text-white'}`}>
              M
            </div>
          )}

          <button
            onClick={onToggle}
            aria-label={isOpen ? 'Collapse sidebar' : 'Expand sidebar'}
            className={`p-1.5 rounded-lg transition-colors ${
              darkMode
                ? 'text-zinc-400 hover:text-white hover:bg-zinc-800'
                : 'text-zinc-500 hover:text-zinc-900 hover:bg-zinc-100'
            }`}
          >
            {isOpen ? <ChevronLeft className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
          </button>
        </div>

        {isOpen && (
          <div className="flex-1 flex flex-col overflow-hidden p-3 space-y-3">
            {/* A2: Keep only this top "New Consultation" button */}
            <button
              onClick={onNewChat}
              className={`w-full flex items-center justify-center gap-2 py-2 px-3.5 rounded-xl font-medium text-xs transition-all duration-150 ${
                darkMode
                  ? 'bg-zinc-100 hover:bg-zinc-200 text-black'
                  : 'bg-zinc-900 hover:bg-zinc-800 text-white'
              }`}
            >
              <Plus className="w-3.5 h-3.5" />
              <span>{t('sidebar.new_consultation', 'New Conversation')}</span>
            </button>

            {activePdf && (
              <div className={`p-2.5 rounded-xl text-xs flex items-center gap-2.5 border ${darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-zinc-50 border-zinc-200'}`}>
                <FileText className={`w-4 h-4 shrink-0 ${darkMode ? 'text-zinc-300' : 'text-zinc-500'}`} />
                <div className="overflow-hidden">
                  <div className={`font-medium truncate ${darkMode ? 'text-white' : 'text-zinc-900'}`}>{activePdf.name}</div>
                  <div className={`text-[10px] ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>{t('sidebar.active_report', 'Active report')}</div>
                </div>
              </div>
            )}

            <div className="relative">
              <Search className={`w-3.5 h-3.5 absolute left-3 top-2.5 ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`} />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t('sidebar.search', 'Search chats...')}
                className={`w-full pl-8 pr-3 py-1.5 text-xs rounded-xl border focus:outline-none transition-all ${
                  darkMode
                    ? 'bg-zinc-900/60 text-white placeholder-zinc-500 border-zinc-800 focus:border-zinc-700'
                    : 'bg-zinc-50 text-zinc-900 placeholder-zinc-400 border-zinc-200 focus:border-zinc-400'
                }`}
              />
            </div>

            {/* HISTORY section — no duplicate "New Consultation" (A2) */}
            <div className="flex-1 overflow-y-auto space-y-0.5 pr-1">
              <div className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-1 ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                {t('sidebar.history', 'History')}
              </div>

              {filteredChats.length === 0 ? (
                <div className={`text-center py-6 text-xs ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>{t('sidebar.no_chats', 'No chats found')}</div>
              ) : (
                filteredChats.map((chat, index) => {
                  const isActive = Boolean(chat.id) && chat.id === activeSessionId;
                  const isRenaming = Boolean(renamingId) && renamingId === chat.id;
                  const isMenuOpen = Boolean(openMenuId) && openMenuId === chat.id;
                  const displayTitle = chat.title || 'New Conversation';

                  return (
                    <div key={chat.id || `chat-${index}`} className="relative group flex items-center w-full min-w-0">
                      {isRenaming ? (
                        /* Inline rename row — replaces the title in place, inside the chat item */
                        <div className="flex-1 flex items-center gap-1 min-w-0">
                          <input
                            ref={renameInputRef}
                            type="text"
                            value={renameValue}
                            onChange={(e) => setRenameValue(e.target.value.slice(0, 60))}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') commitRename(chat.id);
                              if (e.key === 'Escape') cancelRename();
                            }}
                            maxLength={60}
                            aria-label="Rename chat"
                            className="flex-1 min-w-0 text-xs bg-gray-800 text-white px-2 py-1 rounded border border-gray-600 focus:outline-none focus:border-blue-500"
                          />
                          <button
                            type="button"
                            onClick={() => commitRename(chat.id)}
                            aria-label="Confirm rename"
                            className="shrink-0 p-1 rounded text-emerald-400 hover:text-emerald-300 hover:bg-zinc-700/50 transition-colors"
                          >
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={cancelRename}
                            aria-label="Cancel rename"
                            className="shrink-0 p-1 rounded text-zinc-400 hover:text-zinc-200 hover:bg-zinc-700/50 transition-colors"
                          >
                            <X className="w-3.5 h-3.5" />
                          </button>
                        </div>
                      ) : (
                        <>
                          {/* B4: Title + timestamp secondary line */}
                          <button
                            onClick={() => onSelectChat(chat.id)}
                            className={`flex-1 text-left p-2 pr-8 rounded-xl text-xs flex flex-col gap-0.5 transition-colors ${
                              isActive
                                ? darkMode
                                ? 'bg-zinc-800 text-white font-medium border border-zinc-700'
                                : 'bg-zinc-100 text-zinc-900 font-medium border border-zinc-300'
                                : darkMode
                                ? 'text-zinc-400 hover:bg-zinc-900/50 hover:text-white'
                                : 'text-zinc-500 hover:bg-zinc-50 hover:text-zinc-900'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <MessageSquare className="w-3.5 h-3.5 shrink-0 opacity-60" />
                              <span className="truncate flex-1">{displayTitle}</span>
                            </div>
                            {chat.created_at && (
                              <span className={`text-[10px] pl-5 ${darkMode ? 'text-zinc-600' : 'text-zinc-400'}`}>
                                {formatRelativeTime(chat.created_at)}
                              </span>
                            )}
                          </button>

                          {/* B3: 3-dot menu */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              if (!chat.id) return;
                              setOpenMenuId((prev) => (prev === chat.id ? null : chat.id));
                            }}
                            aria-label="Chat options"
                            className={`absolute right-1.5 p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity ${isMenuOpen ? '!opacity-100' : ''} ${
                              darkMode
                                ? 'text-zinc-500 hover:text-white hover:bg-zinc-700'
                                : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'
                            }`}
                          >
                            <MoreHorizontal className="w-3.5 h-3.5" />
                          </button>

                          {/* Dropdown menu */}
                          {isMenuOpen && (
                            <div
                              ref={(el) => {
                                if (chat.id) menuRefs.current[chat.id] = el;
                              }}
                              className={`absolute right-0 top-8 z-50 w-36 rounded-xl shadow-lg border overflow-hidden text-xs ${
                                darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-zinc-200'
                              }`}
                            >
                              <button
                                onClick={() => startRename(chat)}
                                className={`w-full flex items-center gap-2 px-3 py-2 transition-colors ${
                                  darkMode ? 'text-zinc-300 hover:bg-zinc-800 hover:text-white' : 'text-zinc-700 hover:bg-zinc-50'
                                }`}
                              >
                                <Pencil className="w-3.5 h-3.5" />
                                <span>{t('sidebar.rename', 'Rename')}</span>
                              </button>
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  setOpenMenuId(null);
                                  setPendingDeleteId(chat.id);
                                }}
                                className="w-full flex items-center gap-2 px-3 py-2 text-red-400 hover:bg-red-950/40 hover:text-red-300 transition-colors"
                              >
                                <Trash2 className="w-3.5 h-3.5" />
                                <span>{t('sidebar.delete', 'Delete')}</span>
                              </button>
                            </div>
                          )}
                        </>
                      )}
                    </div>
                  );
                })
              )}
            </div>

            {/* A5: Slim footer — Profile & Caregiver Hub + Settings only */}
            <div className={`pt-3 border-t space-y-1 ${darkMode ? 'border-zinc-800' : 'border-zinc-200'}`}>
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
                  <span>{t('sidebar.profile', 'Profile & Caregiver Hub')}</span>
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
                <span>{t('sidebar.settings', 'Settings')}</span>
              </button>

              <button
                onClick={() => setPendingLogout(true)}
                className={`w-full flex items-center gap-2 p-2 rounded-xl text-xs transition-colors ${
                  darkMode
                    ? 'text-zinc-400 hover:bg-zinc-900 hover:text-white'
                    : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-900'
                }`}
              >
                <LogOut className="w-3.5 h-3.5 text-red-400" />
                <span>{t('sidebar.logout', 'Log out')}</span>
              </button>

              {/* A6: End-to-end encrypted badge (not HIPAA claim) */}
              <div className="pt-2 flex items-center gap-2.5 px-2">
                <div className={`w-6 h-6 rounded-full flex items-center justify-center font-bold text-xs ${darkMode ? 'bg-zinc-800 text-zinc-300' : 'bg-zinc-100 text-zinc-600'}`}>
                  <Shield className={`w-3 h-3 ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`} />
                </div>
                <div className="overflow-hidden text-[11px]">
                  <div className={`font-medium truncate ${darkMode ? 'text-white' : 'text-zinc-900'}`}>
                    {currentUser?.full_name || (currentUser?.email ? currentUser.email.split('@')[0] : 'Patient Session')}
                  </div>
                  <div className={`text-[10px] truncate ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                    {t('sidebar.encrypted', 'End-to-end encrypted')}
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </aside>

      {/* Delete chat confirmation modal */}
      <ConfirmModal
        isOpen={!!pendingDeleteId}
        onClose={() => setPendingDeleteId(null)}
        onConfirm={handleDeleteConfirmed}
        title="Delete this conversation?"
        body="This will permanently delete the chat history and any patient context linked to this session. This action cannot be undone."
        confirmLabel="Delete"
        requireTyping={null}
        closeable={true}
        darkMode={darkMode}
      />

      {/* Logout confirmation modal */}
      <ConfirmModal
        isOpen={pendingLogout}
        onClose={() => setPendingLogout(false)}
        onConfirm={() => {
          setPendingLogout(false);
          if (onLogout) onLogout();
        }}
        title="Log out of MediSkye?"
        body="You will be returned to the login screen and any locally cached health data on this device will be cleared."
        confirmLabel="Log out"
        requireTyping={null}
        closeable={true}
        darkMode={darkMode}
      />
    </>
  );
}
