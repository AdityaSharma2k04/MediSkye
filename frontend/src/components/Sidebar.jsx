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
} from 'lucide-react';
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
  const [searchQuery, setSearchQuery] = useState('');
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef(null);
  const menuRef = useRef(null);

  const filteredChats = conversations.filter((c) =>
    (c.title || 'New Consultation').toLowerCase().includes(searchQuery.toLowerCase())
  );

  // Close menu when clicking outside
  useEffect(() => {
    const handler = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) {
        setOpenMenuId(null);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

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
    setRenameValue(chat.title || 'New Consultation');
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
        className={`fixed lg:static inset-y-0 left-0 z-40 flex flex-col transition-all duration-300 ease-in-out border-r ${
          darkMode
            ? 'bg-[#09090B] border-zinc-800/80'
            : 'bg-white border-zinc-200'
        } ${isOpen ? 'w-64 sm:w-72' : 'w-0 lg:w-16 overflow-hidden'}`}
      >
        <div className={`p-4 flex items-center justify-between border-b ${darkMode ? 'border-zinc-800/80' : 'border-zinc-200'}`}>
          {isOpen ? (
            <div className="flex items-center gap-2.5">
              <div className={`w-7 h-7 rounded-xl flex items-center justify-center font-bold text-xs ${darkMode ? 'bg-zinc-100 text-black' : 'bg-zinc-900 text-white'}`}>
                <Activity className="w-3.5 h-3.5" />
              </div>
              <div>
                <h1 className={`font-semibold text-sm tracking-tight ${darkMode ? 'text-white' : 'text-zinc-900'}`}>MediSkye AI</h1>
                <span className={`text-[10px] font-medium uppercase tracking-wider block ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>
                  Medical Assistant
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
              <span>New Consultation</span>
            </button>

            {activePdf && (
              <div className={`p-2.5 rounded-xl text-xs flex items-center gap-2.5 border ${darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-zinc-50 border-zinc-200'}`}>
                <FileText className={`w-4 h-4 shrink-0 ${darkMode ? 'text-zinc-300' : 'text-zinc-500'}`} />
                <div className="overflow-hidden">
                  <div className={`font-medium truncate ${darkMode ? 'text-white' : 'text-zinc-900'}`}>{activePdf.name}</div>
                  <div className={`text-[10px] ${darkMode ? 'text-zinc-400' : 'text-zinc-500'}`}>Active report</div>
                </div>
              </div>
            )}

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

            {/* HISTORY section — no duplicate "New Consultation" (A2) */}
            <div className="flex-1 overflow-y-auto space-y-0.5 pr-1">
              <div className={`text-[10px] font-semibold uppercase tracking-wider px-2 py-1 ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>
                History
              </div>

              {filteredChats.length === 0 ? (
                <div className={`text-center py-6 text-xs ${darkMode ? 'text-zinc-500' : 'text-zinc-400'}`}>No chats found</div>
              ) : (
                filteredChats.map((chat) => {
                  const isActive = chat.id === activeSessionId;
                  const isRenaming = renamingId === chat.id;
                  const displayTitle = chat.title || 'New Consultation';

                  return (
                    <div key={chat.id} className="relative group flex items-center w-full" ref={openMenuId === chat.id ? menuRef : null}>
                      {isRenaming ? (
                        /* Inline rename input */
                        <div className={`flex-1 flex items-center gap-1 p-1.5 rounded-xl border ${
                          darkMode ? 'bg-zinc-800 border-zinc-700' : 'bg-zinc-50 border-zinc-300'
                        }`}>
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
                            className={`flex-1 text-xs bg-transparent focus:outline-none ${
                              darkMode ? 'text-white' : 'text-zinc-900'
                            }`}
                          />
                          <button onClick={() => commitRename(chat.id)} aria-label="Confirm rename" className="text-emerald-400 hover:text-emerald-300 p-0.5">
                            <Check className="w-3.5 h-3.5" />
                          </button>
                          <button onClick={cancelRename} aria-label="Cancel rename" className={`p-0.5 ${darkMode ? 'text-zinc-500 hover:text-zinc-300' : 'text-zinc-400 hover:text-zinc-600'}`}>
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
                            {chat.createdAt && (
                              <span className={`text-[10px] pl-5 ${darkMode ? 'text-zinc-600' : 'text-zinc-400'}`}>
                                {formatRelativeTime(chat.createdAt)}
                              </span>
                            )}
                          </button>

                          {/* B3: 3-dot menu */}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              setOpenMenuId(openMenuId === chat.id ? null : chat.id);
                            }}
                            aria-label="Chat options"
                            className={`absolute right-1.5 p-1 rounded transition-all opacity-0 group-hover:opacity-100 ${
                              isActive ? 'opacity-100' : ''
                            } ${
                              darkMode
                                ? 'text-zinc-500 hover:text-white hover:bg-zinc-700'
                                : 'text-zinc-400 hover:text-zinc-700 hover:bg-zinc-100'
                            }`}
                          >
                            <MoreHorizontal className="w-3.5 h-3.5" />
                          </button>

                          {/* Dropdown menu */}
                          {openMenuId === chat.id && (
                            <div className={`absolute right-0 top-8 z-50 w-36 rounded-xl shadow-lg border overflow-hidden text-xs ${
                              darkMode ? 'bg-zinc-900 border-zinc-800' : 'bg-white border-zinc-200'
                            }`}>
                              <button
                                onClick={() => startRename(chat)}
                                className={`w-full flex items-center gap-2 px-3 py-2 transition-colors ${
                                  darkMode ? 'text-zinc-300 hover:bg-zinc-800 hover:text-white' : 'text-zinc-700 hover:bg-zinc-50'
                                }`}
                              >
                                <Pencil className="w-3.5 h-3.5" />
                                <span>Rename</span>
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
                                <span>Delete</span>
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
                  <span>Profile &amp; Caregiver Hub</span>
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
                    End-to-end encrypted
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
    </>
  );
}
