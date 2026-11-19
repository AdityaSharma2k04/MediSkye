import React from 'react';
import { Plus, Search, Brain, Users, Settings, PanelLeftOpen, Upload } from 'lucide-react';
import { cn } from '../../lib/cn';
import { BrandMark } from './Brand';
import { PatientAvatar } from './PatientSwitcher';

/**
 * Slim 56px desktop rail shown while the history sidebar is collapsed.
 * Keeps the most frequent destinations one click away.
 */
export default function NavRail({ onExpand, onNewChat, onOpenPalette, onUpload, onOpenMemory, onOpenCaregivers, onOpenSettings, currentUser }) {
  const item = 'ms-tap w-10 h-10 rounded-xl flex items-center justify-center text-slate-500 hover:text-slate-900 hover:bg-slate-100 transition';
  return (
    <nav
      data-testid="nav-rail"
      aria-label="Quick navigation"
      className="hidden lg:flex fixed inset-y-0 left-0 z-30 w-14 flex-col items-center py-3 gap-1 border-r border-slate-200 bg-white"
    >
      <div className="mb-2">
        <BrandMark size={32} />
      </div>
      <button type="button" onClick={onExpand} className={item} aria-label="Expand sidebar" title="Expand history">
        <PanelLeftOpen className="w-[18px] h-[18px]" />
      </button>
      <button type="button" onClick={onNewChat} className={cn(item, 'text-cyan-700 hover:text-cyan-800')} aria-label="Start a new chat" title="New conversation">
        <Plus className="w-[18px] h-[18px]" />
      </button>
      <button type="button" onClick={onUpload} className={item} aria-label="Upload a lab report" title="Upload a lab report">
        <Upload className="w-[18px] h-[18px]" />
      </button>
      <button type="button" onClick={onOpenPalette} className={item} aria-label="Open command palette" title="Search and commands (Ctrl K)">
        <Search className="w-[18px] h-[18px]" />
      </button>
      <div className="w-6 h-px bg-slate-200 my-2" />
      <button type="button" onClick={onOpenMemory} className={item} aria-label="Open memory vault" title="Memory vault">
        <Brain className="w-[18px] h-[18px]" />
      </button>
      <button type="button" onClick={onOpenCaregivers} className={item} aria-label="Open caregiver hub" title="Caregiver hub">
        <Users className="w-[18px] h-[18px]" />
      </button>
      <div className="mt-auto flex flex-col items-center gap-1">
        <button type="button" onClick={onOpenSettings} className={item} aria-label="Open settings" title="Settings">
          <Settings className="w-[18px] h-[18px]" />
        </button>
        <span title={currentUser?.email || ''} className="mt-1">
          <PatientAvatar name={currentUser?.full_name || currentUser?.email || 'U'} size="md" />
        </span>
      </div>
    </nav>
  );
}
