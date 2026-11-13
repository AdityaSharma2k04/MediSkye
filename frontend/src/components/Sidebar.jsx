import React, { useState, useRef, useEffect, useMemo } from 'react';
import {
  Plus,
  Search,
  MessageSquare,
  FileText,
  Settings,
  ShieldCheck,
  Users,
  Trash2,
  MoreHorizontal,
  Pencil,
  Check,
  X,
  LogOut,
  Brain,
  PanelLeftClose,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import ConfirmModal from './ConfirmModal';
import { cn } from '../lib/cn';
import { BrandLockup } from './workbench/Brand';
import { PatientAvatar } from './workbench/PatientSwitcher';
import Kbd from './ui/Kbd';
import { MOD_LABEL } from '../hooks/useHotkeys';

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
  onOpenMemory,
  onOpenPalette,
  activePdf, // eslint-disable-line no-unused-vars
  onLogout,
  onDeleteChat,
  onRenameChat,
  currentUser,
  dependents = [],
}) {
  const { t } = useTranslation();
  const [searchQuery, setSearchQuery] = useState('');
  const [pendingDeleteId, setPendingDeleteId] = useState(null);
  const [pendingLogout, setPendingLogout] = useState(false);
  const [openMenuId, setOpenMenuId] = useState(null);
  const [renamingId, setRenamingId] = useState(null);
  const [renameValue, setRenameValue] = useState('');
  const renameInputRef = useRef(null);
  const menuRefs = useRef({});

  // Guarantee menu is closed on every mount (guards against StrictMode double-invoke)
  useEffect(() => {
    setOpenMenuId(null);
  }, []);

  const dependentIndex = useMemo(() => {
    const m = new Map();
    (dependents || []).forEach((d, i) => m.set(String(d.id), { name: d.full_name, index: i + 1 }));
    return m;
  }, [dependents]);

  // Omit empty untitled placeholder chats from history if they are inactive
  const filteredChats = (conversations || [])
    .filter((c) => {
      const isBlankPlaceholder =
        (c.title === 'New Conversation' || c.title === 'New chat') &&
        Array.isArray(c.messages) &&
        c.messages.length === 0 &&
        !c.pdf &&
        !c.document_id &&
        c.id !== activeSessionId;
      return !isBlankPlaceholder;
    })
    .filter((c) => (c.title || 'New Conversation').toLowerCase().includes(searchQuery.toLowerCase()));

  const reportChats = filteredChats.filter((c) => c.pdf || c.document_id);
  const plainChats = filteredChats.filter((c) => !(c.pdf || c.document_id));

  // Close menu when clicking outside or pressing Escape
  useEffect(() => {
    if (!openMenuId) return undefined;
    const handleMouseDown = (e) => {
      const ref = menuRefs.current[openMenuId];
      if (ref && !ref.contains(e.target)) setOpenMenuId(null);
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

  useEffect(() => {
    if (renamingId && renameInputRef.current) {
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [renamingId]);

  const handleDeleteConfirmed = () => {
    if (pendingDeleteId && onDeleteChat) onDeleteChat(pendingDeleteId, /* skipConfirm */ true);
    setPendingDeleteId(null);
  };

  const startRename = (chat) => {
    setOpenMenuId(null);
    setRenamingId(chat.id);
    setRenameValue(chat.title || 'New Conversation');
  };

  const commitRename = (id) => {
    if (renameValue.trim() && onRenameChat) onRenameChat(id, renameValue.trim());
    setRenamingId(null);
  };

  const cancelRename = () => {
    setRenamingId(null);
    setRenameValue('');
  };

  const renderChat = (chat, index) => {
    const isActive = Boolean(chat.id) && chat.id === activeSessionId;
    const isRenaming = Boolean(renamingId) && renamingId === chat.id;
    const isMenuOpen = Boolean(openMenuId) && openMenuId === chat.id;
    const displayTitle = chat.title || 'New Conversation';
    const isReport = Boolean(chat.pdf || chat.document_id);
    const dep = chat.patient_id && chat.patient_id !== 'self' ? dependentIndex.get(String(chat.patient_id)) : null;

    return (
      <div key={chat.id || `chat-${index}`} className="relative group flex items-center w-full min-w-0">
        {isRenaming ? (
          <div className="flex-1 flex items-center gap-1 min-w-0 px-1 py-1">
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
              className="flex-1 min-w-0 h-9 text-[13px] px-2.5 rounded-lg bg-graphite text-white border border-cyan-500/40 focus:outline-none"
            />
            <button
              type="button"
              onClick={() => commitRename(chat.id)}
              aria-label="Confirm rename"
              className="ms-tap shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-emerald-300 hover:bg-white/[0.06]"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
            <button
              type="button"
              onClick={cancelRename}
              aria-label="Cancel rename"
              className="ms-tap shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-ink-mute hover:text-white hover:bg-white/[0.06]"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        ) : (
          <>
            <button
              type="button"
              onClick={() => onSelectChat(chat.id)}
              aria-current={isActive ? 'page' : undefined}
              className={cn(
                'relative flex-1 min-w-0 text-left pl-2.5 pr-9 py-2 rounded-xl text-[13px] flex items-start gap-2.5 transition-colors',
                isActive ? 'bg-white/[0.07] text-white' : 'text-ink-mute hover:bg-white/[0.035] hover:text-ink'
              )}
            >
              {isActive && <span className="absolute left-0 top-2 bottom-2 w-[2px] rounded-full bg-clinical-cyan" aria-hidden="true" />}
              {isReport ? (
                <FileText className={cn('w-4 h-4 mt-px shrink-0', isActive ? 'text-cyan-300' : 'text-ink-faint')} />
              ) : (
                <MessageSquare className={cn('w-4 h-4 mt-px shrink-0', isActive ? 'text-ink-soft' : 'text-ink-faint')} />
              )}
              <span className="min-w-0 flex-1">
                <span className="block truncate font-medium">{displayTitle}</span>
                {(chat.collected_at || chat.created_at || dep) && (
                  <span className="flex items-center gap-1.5 mt-1">
                    {dep && <PatientAvatar name={dep.name} index={dep.index} size="sm" className="!w-4 !h-4 !text-[8px]" />}
                    {chat.collected_at ? (
                      <span className="text-xs ms-num px-1.5 py-px rounded-md bg-cyan-500/10 text-cyan-200/90 border border-cyan-500/15">{chat.collected_at}</span>
                    ) : null}
                    {chat.created_at && <span className="text-xs text-ink-faint">{formatRelativeTime(chat.created_at)}</span>}
                  </span>
                )}
              </span>
            </button>

            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                if (!chat.id) return;
                setOpenMenuId((prev) => (prev === chat.id ? null : chat.id));
              }}
              aria-label="Chat options"
              aria-haspopup="menu"
              aria-expanded={isMenuOpen}
              className={cn(
                'absolute right-1 top-1.5 w-7 h-7 rounded-lg flex items-center justify-center text-ink-mute hover:text-white hover:bg-white/[0.08] transition-opacity',
                'opacity-0 group-hover:opacity-100 focus:opacity-100 [@media(pointer:coarse)]:opacity-100',
                isMenuOpen && '!opacity-100'
              )}
            >
              <MoreHorizontal className="w-4 h-4" />
            </button>

            {isMenuOpen && (
              <div
                ref={(el) => {
                  if (chat.id) menuRefs.current[chat.id] = el;
                }}
                role="menu"
                className="absolute right-0 top-9 z-50 w-40 rounded-xl ms-glass overflow-hidden text-[13px] p-1 animate-slide-in"
              >
                <button
                  type="button"
                  onClick={() => startRename(chat)}
                  className="w-full flex items-center gap-2 px-2.5 h-9 rounded-lg text-ink-soft hover:bg-white/[0.06] hover:text-white transition-colors"
                >
                  <Pencil className="w-3.5 h-3.5" />
                  <span>{t('sidebar.rename', 'Rename')}</span>
                </button>
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    setOpenMenuId(null);
                    setPendingDeleteId(chat.id);
                  }}
                  className="w-full flex items-center gap-2 px-2.5 h-9 rounded-lg text-rose-300 hover:bg-rose-500/10 transition-colors"
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
  };

  const footerBtn = 'ms-tap w-full flex items-center gap-2.5 px-2.5 h-9 rounded-xl text-[13px] text-ink-mute hover:bg-white/[0.04] hover:text-white transition-colors';
  const identity = currentUser?.full_name || (currentUser?.email ? currentUser.email.split('@')[0] : 'Patient Session');

  return (
    <>
      <aside className="w-full h-full flex flex-col border-r border-white/[0.06] bg-obsidian pt-safe">
        <div className="h-14 px-3.5 flex items-center justify-between shrink-0">
          <BrandLockup size={28} subtitle={t('sidebar.medical_assistant', 'Medical Assistant')} />
          {isOpen && onToggle && (
            <button
              type="button"
              onClick={onToggle}
              aria-label="Collapse sidebar"
              title="Collapse sidebar"
              className="ms-tap w-8 h-8 rounded-lg flex items-center justify-center text-ink-faint hover:text-white hover:bg-white/[0.06] transition"
            >
              <PanelLeftClose className="w-4 h-4" />
            </button>
          )}
        </div>

        {isOpen && (
          <div className="flex-1 min-h-0 flex flex-col px-2.5 pb-2.5 gap-3">
            <div className="flex items-center gap-2 px-0.5">
              <button
                type="button"
                onClick={onNewChat}
                className="ms-tap flex-1 flex items-center justify-center gap-2 h-10 px-3 rounded-xl font-semibold text-[13px] bg-clinical-cyan hover:bg-cyan-300 text-slate-950 shadow-[0_8px_24px_-12px_rgba(6,182,212,0.9)] transition active:scale-[0.98]"
              >
                <Plus className="w-4 h-4" />
                <span>{t('sidebar.new_consultation', 'New Conversation')}</span>
              </button>
              {onOpenPalette && (
                <button
                  type="button"
                  onClick={onOpenPalette}
                  aria-label="Open command palette"
                  title={`Search everything (${MOD_LABEL}+K)`}
                  className="ms-tap w-10 h-10 rounded-xl flex items-center justify-center bg-white/[0.03] border border-white/[0.08] text-ink-mute hover:text-white hover:bg-white/[0.06] transition"
                >
                  <Search className="w-4 h-4" />
                </button>
              )}
            </div>

            <div className="relative px-0.5">
              <Search className="w-3.5 h-3.5 absolute left-3.5 top-1/2 -translate-y-1/2 text-ink-faint" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder={t('sidebar.search', 'Search chats...')}
                aria-label="Search chat history"
                className="w-full h-9 pl-8 pr-12 text-[13px] rounded-xl bg-white/[0.03] text-white placeholder:text-ink-faint border border-white/[0.06] focus:outline-none focus:border-white/[0.16] transition"
              />
              <span className="absolute right-2.5 top-1/2 -translate-y-1/2 hidden lg:inline-flex">
                <Kbd>{`${MOD_LABEL} K`}</Kbd>
              </span>
            </div>

            <div className="flex-1 min-h-0 overflow-y-auto -mx-1 px-1 space-y-4">
              {filteredChats.length === 0 ? (
                (conversations || []).length === 0 ? (
                  <div className="flex flex-col items-center text-center py-10 px-3 animate-fade-in">
                    <div className="w-10 h-10 rounded-2xl flex items-center justify-center mb-3 bg-white/[0.04] text-ink-mute">
                      <MessageSquare className="w-5 h-5" />
                    </div>
                    <div className="text-xs font-semibold mb-1 text-ink-soft">{t('sidebar.no_conversations_title', 'No conversations yet')}</div>
                    <div className="text-xs leading-relaxed mb-4 text-ink-faint">
                      {t('sidebar.no_conversations_subtitle', 'Upload a medical report or start a new conversation to see it here.')}
                    </div>
                    <button
                      type="button"
                      onClick={onNewChat}
                      className="px-3 h-8 rounded-lg text-xs font-medium border border-white/[0.1] text-ink-soft hover:bg-white/[0.05] hover:text-white transition"
                    >
                      {t('sidebar.new_consultation', 'New Conversation')}
                    </button>
                  </div>
                ) : (
                  <div className="flex flex-col items-center text-center py-10 px-3 animate-fade-in">
                    <Search className="w-5 h-5 mb-2 text-ink-faint" />
                    <div className="text-xs text-ink-faint">{t('sidebar.no_chats', 'No chats found')}</div>
                  </div>
                )
              ) : (
                <>
                  {reportChats.length > 0 && (
                    <section aria-label="Lab reports">
                      <h3 className="px-2.5 pb-1 text-xs font-semibold text-ink-faint">Lab reports</h3>
                      <div className="space-y-0.5">{reportChats.map(renderChat)}</div>
                    </section>
                  )}
                  {plainChats.length > 0 && (
                    <section aria-label={t('sidebar.history', 'History')}>
                      <h3 className="px-2.5 pb-1 text-xs font-semibold text-ink-faint">{t('sidebar.history', 'History')}</h3>
                      <div className="space-y-0.5">{plainChats.map(renderChat)}</div>
                    </section>
                  )}
                </>
              )}
            </div>

            <div className="pt-2 border-t border-white/[0.06] space-y-0.5">
              {onOpenMemory && (
                <button type="button" onClick={onOpenMemory} className={footerBtn}>
                  <Brain className="w-4 h-4 text-violet-300" />
                  <span>Memory vault</span>
                </button>
              )}
              <button type="button" onClick={onOpenProfile} className={footerBtn}>
                <Users className="w-4 h-4 text-cyan-300" />
                <span>{t('sidebar.profile', 'Profile & Caregiver Hub')}</span>
              </button>
              <button type="button" onClick={onOpenSettings} className={footerBtn}>
                <Settings className="w-4 h-4" />
                <span>{t('sidebar.settings', 'Settings')}</span>
              </button>
              <button type="button" onClick={() => setPendingLogout(true)} className={footerBtn}>
                <LogOut className="w-4 h-4 text-rose-400" />
                <span>{t('sidebar.logout', 'Log out')}</span>
              </button>

              <div className="mt-1.5 flex items-center gap-2.5 px-2 py-2 rounded-xl bg-white/[0.02] border border-white/[0.05]">
                <PatientAvatar name={identity} size="md" />
                <div className="min-w-0 text-xs">
                  <div className="font-medium truncate text-ink">{identity}</div>
                  <div className="flex items-center gap-1 text-xs truncate text-ink-faint">
                    <ShieldCheck className="w-3 h-3 shrink-0 text-emerald-400/80" />
                    <span className="truncate">{t('sidebar.encrypted', 'Encrypted at rest (Fernet) • TLS 1.3 in transit')}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}
      </aside>

      <ConfirmModal
        isOpen={!!pendingDeleteId}
        onClose={() => setPendingDeleteId(null)}
        onConfirm={handleDeleteConfirmed}
        title="Delete this conversation?"
        body="This will permanently delete the chat history and any patient context linked to this session. This action cannot be undone."
        confirmLabel="Delete"
        requireTyping={null}
        closeable={true}
        darkMode
      />

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
        darkMode
      />
    </>
  );
}
