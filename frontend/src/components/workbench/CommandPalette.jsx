import React, { useEffect, useMemo, useState } from 'react';
import { Command } from 'cmdk';
import * as Dialog from '@radix-ui/react-dialog';
import {
  Search,
  Plus,
  Upload,
  FileText,
  MessageSquare,
  Printer,
  Download,
  PanelRight,
  PanelLeft,
  Brain,
  Settings,
  Users,
  Languages,
  LogOut,
  FlaskConical,
  Sparkles,
  CornerDownLeft,
  LineChart,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import Kbd from '../ui/Kbd';
import { MOD_LABEL } from '../../hooks/useHotkeys';
import { metricName, metricKey, statusTone, TONE, reportLabel, reportDateLabel } from '../../lib/clinical';
import { PatientAvatar, buildPatients, isSelfSelected } from './PatientSwitcher';

/**
 * Ctrl/⌘ + K command palette.
 * Everything a power user needs without leaving the keyboard: jump to a
 * report or conversation, switch patient, find a biomarker, change
 * language, export, or just type a question and send it.
 */
export default function CommandPalette({
  open,
  onOpenChange,
  conversations = [],
  activeSessionId,
  metrics = [],
  currentUser,
  dependents = [],
  selectedPatientId,
  uiLanguage = 'en',
  hasActiveReport = false,
  actions = {},
}) {
  const { t } = useTranslation();
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (!open) setQuery('');
  }, [open]);

  const run = (fn) => () => {
    onOpenChange(false);
    // Let the dialog unmount before focusing whatever the action opens
    setTimeout(() => fn?.(), 0);
  };

  const reports = useMemo(() => conversations.filter((c) => c.document_id || c.pdf), [conversations]);
  const chats = useMemo(
    () => conversations.filter((c) => !c.document_id && !c.pdf && Array.isArray(c.messages) && c.messages.length > 0),
    [conversations]
  );
  const patients = buildPatients(currentUser, dependents);
  const selfSelected = isSelfSelected(selectedPatientId, currentUser);

  const item = 'flex items-center gap-3 px-3 h-10 mx-1.5 rounded-xl text-[13px] text-ink-soft';
  const iconCls = 'w-4 h-4 text-ink-mute shrink-0';

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-[70] bg-black/55 backdrop-blur-[3px] animate-backdrop-in" />
        <Dialog.Content
          data-testid="command-palette"
          className="fixed z-[71] inset-x-0 mx-auto top-[12dvh] w-[min(640px,calc(100vw-24px))] rounded-3xl ms-glass overflow-hidden animate-modal-in outline-none"
          aria-describedby={undefined}
        >
          <Dialog.Title className="sr-only">Command palette</Dialog.Title>
          <Command label="Command palette" loop className="flex flex-col max-h-[min(560px,72dvh)]">
            <div className="flex items-center gap-3 px-4 h-14 border-b border-white/[0.07] shrink-0">
              <Search className="w-4 h-4 text-ink-mute" />
              <Command.Input
                autoFocus
                value={query}
                onValueChange={setQuery}
                placeholder={t('workbench.palette_placeholder', 'Search reports, biomarkers, patients, or type a question…')}
                className="flex-1 bg-transparent text-[15px] text-white placeholder:text-ink-faint outline-none border-0 focus:ring-0"
              />
              <Kbd>Esc</Kbd>
            </div>

            <Command.List className="overflow-y-auto overscroll-contain py-1.5">
              <Command.Empty className="py-10 text-center text-sm text-ink-mute">No matches. Press Enter to ask MediSkye instead.</Command.Empty>

              {query.trim().length > 2 && actions.ask && (
                <Command.Group heading="Ask">
                  <Command.Item value={`ask ${query}`} onSelect={run(() => actions.ask(query.trim()))} className={item}>
                    <Sparkles className="w-4 h-4 text-cyan-300 shrink-0" />
                    <span className="truncate">
                      Ask MediSkye: <span className="text-white">{query.trim()}</span>
                    </span>
                    <CornerDownLeft className="ml-auto w-3.5 h-3.5 text-ink-faint" />
                  </Command.Item>
                </Command.Group>
              )}

              <Command.Group heading="Actions">
                <Command.Item value="new conversation chat" onSelect={run(actions.newChat)} className={item}>
                  <Plus className={iconCls} /> New conversation <Shortcut keys={[MOD_LABEL, 'Shift', 'O']} />
                </Command.Item>
                <Command.Item value="upload lab report pdf" onSelect={run(actions.upload)} className={item}>
                  <Upload className={iconCls} /> Upload a lab report <Shortcut keys={[MOD_LABEL, 'U']} />
                </Command.Item>
                {hasActiveReport && (
                  <>
                    <Command.Item value="print physician summary pdf export doctor" onSelect={run(actions.printSummary)} className={item}>
                      <Printer className={iconCls} /> Print physician summary <Shortcut keys={[MOD_LABEL, 'Shift', 'P']} />
                    </Command.Item>
                    <Command.Item value="open lab metrics table inspector" onSelect={run(() => actions.openInspector?.('metrics'))} className={item}>
                      <FlaskConical className={iconCls} /> Open lab metrics
                    </Command.Item>
                    <Command.Item value="open trends longitudinal chart" onSelect={run(() => actions.openInspector?.('trends'))} className={item}>
                      <LineChart className={iconCls} /> Open longitudinal trends
                    </Command.Item>
                  </>
                )}
                <Command.Item value="export chat transcript json pdf download" onSelect={run(actions.exportChat)} className={item}>
                  <Download className={iconCls} /> Export chat transcript
                </Command.Item>
                {actions.toggleInspector && (
                  <Command.Item value="toggle inspector panel split view" onSelect={run(actions.toggleInspector)} className={item}>
                    <PanelRight className={iconCls} /> Toggle clinical inspector <Shortcut keys={[MOD_LABEL, '\\']} />
                  </Command.Item>
                )}
                <Command.Item value="toggle sidebar history navigation" onSelect={run(actions.toggleSidebar)} className={item}>
                  <PanelLeft className={iconCls} /> Toggle history sidebar <Shortcut keys={[MOD_LABEL, 'B']} />
                </Command.Item>
                <Command.Item value="memory vault remembered facts" onSelect={run(actions.openMemory)} className={item}>
                  <Brain className={iconCls} /> Open memory vault <Shortcut keys={[MOD_LABEL, 'Shift', 'M']} />
                </Command.Item>
                <Command.Item value="caregiver hub dependents family profile" onSelect={run(actions.openCaregivers)} className={item}>
                  <Users className={iconCls} /> Caregiver hub & profiles
                </Command.Item>
                <Command.Item value="settings preferences" onSelect={run(actions.openSettings)} className={item}>
                  <Settings className={iconCls} /> Settings <Shortcut keys={[MOD_LABEL, ',']} />
                </Command.Item>
                <Command.Item
                  value="language english hindi हिंदी toggle"
                  onSelect={run(() => actions.setUiLanguage?.(uiLanguage === 'hi' ? 'en' : 'hi'))}
                  className={item}
                >
                  <Languages className={iconCls} />
                  {uiLanguage === 'hi' ? 'Switch interface to English' : 'Switch interface to हिंदी (Hindi)'}
                  <span className="ml-auto ms-num text-[10px] text-ink-faint">{uiLanguage.toUpperCase()}</span>
                </Command.Item>
              </Command.Group>

              {patients.length > 1 && (
                <Command.Group heading="Patients">
                  {patients.map((p, i) => {
                    const isActive = i === 0 ? selfSelected : !selfSelected && String(p.id) === String(selectedPatientId);
                    return (
                      <Command.Item key={p.id} value={`patient ${p.name} ${p.relationship}`} onSelect={run(() => actions.selectPatient?.(p.id))} className={item}>
                        <PatientAvatar name={p.name} index={i} size="sm" />
                        <span className="truncate">{p.name}</span>
                        <span className="text-[11px] text-ink-faint">{p.relationship}</span>
                        {isActive && <span className="ml-auto text-[10px] text-emerald-300">Active</span>}
                      </Command.Item>
                    );
                  })}
                </Command.Group>
              )}

              {metrics.length > 0 && (
                <Command.Group heading="Biomarkers in this report">
                  {metrics.map((m, i) => {
                    const tone = TONE[statusTone(m)];
                    return (
                      <Command.Item
                        key={`${metricKey(m)}-${i}`}
                        value={`biomarker ${metricName(m)} ${m.status || ''}`}
                        onSelect={run(() => actions.focusMetric?.(m))}
                        className={item}
                      >
                        <span className={cn('w-2 h-2 rounded-full shrink-0', tone.dot)} />
                        <span className="truncate">{metricName(m)}</span>
                        <span className={cn('ml-auto ms-num text-xs', tone.text)}>
                          {m.value} <span className="text-ink-faint">{m.unit}</span>
                        </span>
                      </Command.Item>
                    );
                  })}
                </Command.Group>
              )}

              {reports.length > 0 && (
                <Command.Group heading="Lab reports">
                  {reports.map((c) => (
                    <Command.Item key={c.id} value={`report ${c.title || ''} ${c.pdf?.filename || ''} ${c.id}`} onSelect={run(() => actions.selectChat?.(c.id))} className={item}>
                      <FileText className={iconCls} />
                      <span className="truncate">{reportLabel({ title: c.title, filename: c.pdf?.filename })}</span>
                      <span className="ml-auto text-[11px] text-ink-faint shrink-0">
                        {c.id === activeSessionId ? 'Open now' : reportDateLabel({ collected_at: c.collected_at, created_at: c.created_at })}
                      </span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}

              {chats.length > 0 && (
                <Command.Group heading="Conversations">
                  {chats.map((c) => (
                    <Command.Item key={c.id} value={`conversation ${c.title || ''} ${c.id}`} onSelect={run(() => actions.selectChat?.(c.id))} className={item}>
                      <MessageSquare className={iconCls} />
                      <span className="truncate">{c.title || 'Conversation'}</span>
                    </Command.Item>
                  ))}
                </Command.Group>
              )}

              {actions.logout && (
                <Command.Group heading="Account">
                  <Command.Item value="log out sign out" onSelect={run(actions.logout)} className={cn(item, 'text-rose-300')}>
                    <LogOut className="w-4 h-4 text-rose-400 shrink-0" /> Sign out of MediSkye
                  </Command.Item>
                </Command.Group>
              )}
            </Command.List>

            <div className="hidden sm:flex items-center gap-4 px-4 h-10 border-t border-white/[0.07] text-[11px] text-ink-faint shrink-0">
              <span className="inline-flex items-center gap-1.5"><Kbd>↑</Kbd><Kbd>↓</Kbd> navigate</span>
              <span className="inline-flex items-center gap-1.5"><Kbd>↵</Kbd> open</span>
              <span className="ml-auto inline-flex items-center gap-1.5"><Kbd>{MOD_LABEL}</Kbd><Kbd>K</Kbd> toggle</span>
            </div>
          </Command>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function Shortcut({ keys }) {
  return (
    <span className="ml-auto hidden sm:inline-flex items-center gap-1">
      {keys.map((k) => (
        <Kbd key={k}>{k}</Kbd>
      ))}
    </span>
  );
}
