import React, { useEffect, useRef, useState } from 'react';
import {
  Menu,
  Printer,
  Download,
  FlaskConical,
  Search,
  MoreHorizontal,
  MessageSquare,
  Activity,
  FileText,
  Brain,
  Users,
  Settings,
  Languages,
  UploadCloud,
  X,
} from 'lucide-react';
import { useTranslation } from 'react-i18next';
import { cn } from '../../lib/cn';
import ChatWindow from '../ChatWindow';
import ChatInput from '../ChatInput';
import PrintableSummary from '../PrintableSummary';
import InspectorPanel, { INSPECTOR_TABS } from './InspectorPanel';
import PatientSwitcher from './PatientSwitcher';
import UploadStepper from './UploadStepper';
import { BrandMark } from './Brand';
import SegmentedControl from '../ui/SegmentedControl';
import IconButton from '../ui/IconButton';
import Kbd from '../ui/Kbd';
import Sheet from '../ui/Sheet';
import useResizablePane from '../../hooks/useResizablePane';
import { MOD_LABEL } from '../../hooks/useHotkeys';
import { STORAGE_KEYS } from '../../lib/storageKeys';
import { getProfile } from '../../services/api';
import { reportDateLabel } from '../../lib/clinical';

const MOBILE_VIEW_TABS = {
  metrics: INSPECTOR_TABS.filter((t) => t.value === 'metrics' || t.value === 'report'),
  analytics: INSPECTOR_TABS.filter((t) => t.value === 'overview' || t.value === 'trends'),
};

/**
 * The clinical workbench: header + conversation column + (desktop) resizable
 * inspector pane, or (mobile/tablet) a single view switched by a segmented
 * control with the composer hidden on analytic views.
 */
export default function Workbench(props) {
  const {
    isDesktop,
    isMobile,
    toggleSidebar,
    currentUser,
    dependents,
    selectedPatientId,
    onSelectPatient,
    onOpenDependents,
    activePatient,
    patientName,
    reportCounts,
    messages,
    isGenerating,
    loadingHistory,
    onRegenerate,
    onSendMessage,
    onTrySampleReport,
    onAttachFile,
    onStopGeneration,
    chatInputRef,
    composerDocuments,
    onDetachDocument,
    onRemoveFile,
    activePdf,
    documentId,
    attachedDocuments,
    metrics,
    metricsLoading,
    metricsError,
    onReloadMetrics,
    ensureMetrics,
    trends,
    inspectorOpen,
    onToggleInspector,
    inspectorTab,
    onInspectorTabChange,
    metricsFilter,
    onMetricsFilterChange,
    metricsSearch,
    onMetricsSearchChange,
    highlightKey,
    onFocusMetric,
    onAskAbout,
    viewMode,
    onViewModeChange,
    uploadState,
    onDismissUpload,
    uploadError,
    onDismissUploadError,
    isExportingSummary,
    printSummaryText,
    onExportSummary,
    onOpenExport,
    onOpenPalette,
    onOpenSettings,
    onOpenMemory,
    onOpenProfile,
    uiLanguage,
    onSetUiLanguage,
    printSignal,
  } = props;

  const { t } = useTranslation();
  const containerRef = useRef(null);
  const inspectorVisible = isDesktop && inspectorOpen && Boolean(activePdf);
  const pane = useResizablePane({ storageKey: STORAGE_KEYS.inspectorWidth, defaultWidth: 440, min: 340, max: 760, containerRef, active: inspectorVisible });
  const [showPrintSummary, setShowPrintSummary] = useState(false);
  const [printMetrics, setPrintMetrics] = useState(null);
  const [printUser, setPrintUser] = useState(null);
  const [moreOpen, setMoreOpen] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const dragDepth = useRef(0);

  const mobileAnalytic = !isDesktop && activePdf && (viewMode === 'metrics' || viewMode === 'analytics');

  // When the active report goes away, return mobile users to the conversation
  useEffect(() => {
    if (!activePdf && viewMode !== 'chat') onViewModeChange('chat');
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activePdf]);

  // Keep the mobile tab inside the subset that the current view offers
  useEffect(() => {
    if (!mobileAnalytic) return;
    const allowed = MOBILE_VIEW_TABS[viewMode].map((x) => x.value);
    if (!allowed.includes(inspectorTab)) onInspectorTabChange(allowed[0]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mobileAnalytic, viewMode]);

  // ── 1-click physician summary (A4 print) ──
  const handlePrintDoctorSummary = async () => {
    if (isExportingSummary) return;

    let resolvedUser = activePatient || currentUser;
    if (!resolvedUser) {
      try {
        resolvedUser = await getProfile();
      } catch (_) {
        resolvedUser = null;
      }
    }
    setPrintUser(resolvedUser);

    let m = metrics;
    if (documentId && (!Array.isArray(m) || m.length === 0) && ensureMetrics) {
      try {
        m = await ensureMetrics();
      } catch (_) {
        m = [];
      }
    }
    setPrintMetrics(Array.isArray(m) ? m : []);

    if (onExportSummary) await onExportSummary();

    setShowPrintSummary(true);
    setTimeout(() => {
      const origTitle = document.title;
      const name = resolvedUser?.full_name || resolvedUser?.name || (resolvedUser?.email ? resolvedUser.email.split('@')[0] : 'Patient');
      const docTitle = activePdf?.title || activePdf?.name || activePdf?.filename || 'Lab Report';
      document.title = `${name} - ${docTitle} - Clinical Summary`;
      let fallbackTimer = null;
      const cleanup = () => {
        if (fallbackTimer) clearTimeout(fallbackTimer);
        document.title = origTitle;
        setShowPrintSummary(false);
        window.removeEventListener('afterprint', cleanup);
      };
      window.addEventListener('afterprint', cleanup);
      window.print();
      fallbackTimer = setTimeout(cleanup, 60000);
    }, 150);
  };

  // Command palette / keyboard shortcut trigger
  const lastSignal = useRef(printSignal);
  useEffect(() => {
    if (printSignal !== lastSignal.current) {
      lastSignal.current = printSignal;
      if (activePdf) handlePrintDoctorSummary();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [printSignal]);

  // ── Drag & drop upload on the conversation column ──
  const hasFiles = (e) => Array.from(e.dataTransfer?.types || []).includes('Files');
  const onDragEnter = (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth.current += 1;
    setDragActive(true);
  };
  const onDragOver = (e) => {
    if (hasFiles(e)) e.preventDefault();
  };
  const onDragLeave = (e) => {
    if (!hasFiles(e)) return;
    dragDepth.current = Math.max(0, dragDepth.current - 1);
    if (dragDepth.current === 0) setDragActive(false);
  };
  const onDrop = (e) => {
    if (!hasFiles(e)) return;
    e.preventDefault();
    dragDepth.current = 0;
    setDragActive(false);
    const file = e.dataTransfer.files?.[0];
    if (file) onAttachFile(file);
  };

  const openUpload = () => chatInputRef.current?.openFileUpload();

  const inspectorShared = {
    metrics,
    metricsLoading,
    metricsError,
    onReloadMetrics,
    trends,
    activePdf,
    attachedDocuments,
    metricsFilter,
    onMetricsFilterChange,
    metricsSearch,
    onMetricsSearchChange,
    highlightKey,
    onFocusMetric,
    onAskAbout,
    onPrintSummary: handlePrintDoctorSummary,
    isExporting: isExportingSummary,
    onExportChat: onOpenExport,
    onUpload: openUpload,
  };

  const reportDate = reportDateLabel(activePdf);

  return (
    <div className="flex-1 min-h-0 flex flex-col h-full">
      {/* ━━━ Header ━━━ */}
      <header data-testid="workbench-header" className="shrink-0 z-20 border-b border-white/[0.06] bg-obsidian/85 backdrop-blur-xl pt-safe">
        <div className="h-14 px-2 sm:px-3 flex items-center gap-1.5 sm:gap-2">
          {!isDesktop && (
            <IconButton label="Toggle sidebar" onClick={toggleSidebar} className="shrink-0">
              <Menu className="w-[18px] h-[18px]" />
            </IconButton>
          )}

          {!isDesktop && !isMobile && <BrandMark size={26} className="shrink-0 mr-0.5" />}

          {currentUser && (
            <PatientSwitcher
              currentUser={currentUser}
              dependents={dependents}
              selectedPatientId={selectedPatientId}
              onSelectPatient={onSelectPatient}
              onOpenDependents={onOpenDependents}
              reportCounts={reportCounts}
            />
          )}

          {isDesktop && activePdf && (
            <div className="hidden xl:flex items-center gap-2 min-w-0 pl-2 ml-1 border-l border-white/[0.07]">
              <FileText className="w-3.5 h-3.5 text-cyan-300 shrink-0" />
              <span className="text-xs text-ink-soft truncate max-w-[240px]">{`${activePdf.filename || activePdf.name || 'Lab report'}`}</span>
              {reportDate && <span className="ms-num text-[11px] text-ink-faint shrink-0">{`Collected ${reportDate}`}</span>}
            </div>
          )}

          <div className="ml-auto flex items-center gap-1 sm:gap-1.5 shrink-0">
            {isDesktop ? (
              <button
                type="button"
                onClick={onOpenPalette}
                aria-label="Open command palette"
                className="ms-tap inline-flex items-center gap-2 h-9 pl-3 pr-1.5 rounded-xl bg-white/[0.03] border border-white/[0.08] text-xs text-ink-mute hover:text-white hover:border-white/[0.14] transition"
              >
                <Search className="w-3.5 h-3.5" />
                <span className="mr-6 hidden xl:inline">{t('workbench.search_or_jump', 'Search or jump to…')}</span>
                <Kbd>{MOD_LABEL} K</Kbd>
              </button>
            ) : (
              <IconButton label="Open command palette" onClick={onOpenPalette}>
                <Search className="w-[18px] h-[18px]" />
              </IconButton>
            )}

            {isDesktop && activePdf && (
              <button
                type="button"
                onClick={() => onToggleInspector('metrics')}
                aria-label="View extracted lab metrics table"
                aria-pressed={inspectorVisible}
                title={`Clinical inspector (${MOD_LABEL}+\\)`}
                className={cn(
                  'ms-tap inline-flex items-center gap-1.5 h-9 px-3 rounded-xl border text-xs font-medium transition',
                  inspectorVisible ? 'bg-cyan-500/15 border-cyan-500/35 text-cyan-100' : 'bg-white/[0.03] border-white/[0.08] text-ink-soft hover:text-white'
                )}
              >
                <FlaskConical className="w-3.5 h-3.5" />
                <span className="hidden xl:inline">{t('chat.lab_metrics', 'Lab Metrics')}</span>
              </button>
            )}

            {isDesktop && activePdf && (
              <IconButton
                tone="outline"
                onClick={handlePrintDoctorSummary}
                disabled={isExportingSummary}
                label="Export Summary"
                title={isExportingSummary ? t('chat.preparing_summary', 'Preparing Summary...') : 'Print a 2-page A4 physician summary'}
              >
                <Printer className={cn('w-4 h-4', isExportingSummary && 'animate-pulse')} />
              </IconButton>
            )}

            {isDesktop && onOpenExport && (
              <IconButton tone="outline" onClick={onOpenExport} label="Export chat data" title="Export full chat transcript and lab metrics (PDF or JSON)">
                <Download className="w-4 h-4" />
              </IconButton>
            )}

            {!isDesktop && (
              <IconButton label={t('workbench.more_actions', 'More actions')} onClick={() => setMoreOpen(true)}>
                <MoreHorizontal className="w-[18px] h-[18px]" />
              </IconButton>
            )}
          </div>
        </div>

        {!isDesktop && activePdf && (
          <div className="px-3 pb-2.5" data-testid="mobile-view-switcher">
            <SegmentedControl
              fullWidth
              size="sm"
              layoutId="mobile-view"
              value={viewMode}
              onChange={onViewModeChange}
              options={[
                { value: 'chat', label: t('chat.view_chat', 'Chat'), icon: MessageSquare, ariaLabel: 'Switch to chat view' },
                { value: 'metrics', label: t('chat.lab_metrics', 'Lab Metrics'), icon: FlaskConical, ariaLabel: 'View extracted lab metrics table' },
                { value: 'analytics', label: t('workbench.insights', 'Insights'), icon: Activity, ariaLabel: 'View clinical insights and trends' },
              ]}
            />
          </div>
        )}
      </header>

      {/* ━━━ Body ━━━ */}
      <div ref={containerRef} className="flex-1 min-h-0 flex relative">
        <section
          data-testid="conversation-pane"
          aria-label="Conversation"
          className={cn('relative flex-1 min-w-0 flex flex-col', mobileAnalytic && 'hidden')}
          onDragEnter={onDragEnter}
          onDragOver={onDragOver}
          onDragLeave={onDragLeave}
          onDrop={onDrop}
        >
          <ChatWindow
            messages={messages}
            isGenerating={isGenerating}
            loadingHistory={loadingHistory}
            onRegenerate={onRegenerate}
            onSelectSampleQuery={onSendMessage}
            onTrySampleReport={onTrySampleReport}
            activePdf={activePdf}
            currentUser={currentUser}
            patientName={patientName}
            metrics={metrics}
          />

          {(uploadError || uploadState) && (
            <div className="w-full max-w-3xl mx-auto px-3 sm:px-6 pb-1.5 space-y-2">
              {uploadError && (
                <div role="alert" className="flex items-center justify-between gap-2.5 px-3.5 py-2.5 rounded-2xl text-xs font-medium bg-rose-500/10 border border-rose-500/25 text-rose-200 animate-fade-in">
                  <span>{uploadError}</span>
                  <button type="button" onClick={onDismissUploadError} aria-label="Dismiss upload error" className="w-7 h-7 rounded-lg flex items-center justify-center text-rose-200 hover:text-white hover:bg-white/[0.06]">
                    <X className="w-3.5 h-3.5" />
                  </button>
                </div>
              )}
              {uploadState && <UploadStepper upload={uploadState} onDismiss={onDismissUpload} />}
            </div>
          )}

          {/* Composer: always mounted (its file input is the upload entry point); hidden on mobile analytic views */}
          <div className="shrink-0">
            <ChatInput
              ref={chatInputRef}
              onSendMessage={onSendMessage}
              onAttachFile={onAttachFile}
              activeFile={activePdf}
              attachedDocuments={composerDocuments}
              onDetachDocument={onDetachDocument}
              onRemoveFile={onRemoveFile}
              isGenerating={isGenerating}
              onStopGeneration={onStopGeneration}
            />
          </div>

          {dragActive && (
            <div className="absolute inset-3 z-30 rounded-3xl border-2 border-dashed border-cyan-400/60 bg-cyan-500/[0.07] backdrop-blur-sm flex flex-col items-center justify-center text-center pointer-events-none animate-fade-in">
              <UploadCloud className="w-8 h-8 text-cyan-300 mb-2" />
              <div className="ms-display text-xl text-white">{t('workbench.drop_to_analyze', 'Drop to analyze')}</div>
              <div className="text-xs text-ink-mute mt-1">{t('workbench.drop_hint', 'PDF, JPG or PNG up to 50 MB')}</div>
            </div>
          )}
        </section>

        {mobileAnalytic && (
          <section data-testid="mobile-insights-view" aria-label="Clinical insights" className="flex-1 min-w-0 flex flex-col">
            <InspectorPanel
              {...inspectorShared}
              variant="screen"
              layout={isMobile ? 'auto' : 'table'}
              tabs={MOBILE_VIEW_TABS[viewMode]}
              tab={MOBILE_VIEW_TABS[viewMode].some((x) => x.value === inspectorTab) ? inspectorTab : MOBILE_VIEW_TABS[viewMode][0].value}
              onTabChange={onInspectorTabChange}
            />
          </section>
        )}

        {inspectorVisible && (
          <>
            <div
              {...pane.handleProps}
              data-testid="inspector-resize-handle"
              className={cn(
                'group relative w-[9px] -mx-1 z-10 shrink-0 cursor-col-resize flex items-stretch justify-center outline-none touch-none select-none',
                'focus-visible:[&>span]:bg-cyan-400'
              )}
            >
              <span className={cn('w-px h-full transition-colors', pane.isDragging ? 'bg-cyan-400' : 'bg-white/[0.07] group-hover:bg-cyan-500/60')} />
            </div>
            <aside data-testid="inspector-pane" aria-label="Clinical inspector" style={{ width: pane.width }} className="shrink-0 min-h-0 flex flex-col animate-fade-in">
              <InspectorPanel
                {...inspectorShared}
                variant="pane"
                layout={pane.width >= 640 ? 'table' : 'list'}
                compactTabs={pane.width < 420}
                tab={inspectorTab}
                onTabChange={onInspectorTabChange}
                onClose={() => onToggleInspector(null, false)}
              />
            </aside>
          </>
        )}
      </div>

      {/* Mobile overflow actions */}
      {!isDesktop && (
        <Sheet open={moreOpen} onOpenChange={setMoreOpen} title="Actions" icon={MoreHorizontal} variant="center" width={420}>
          <div className="p-3 space-y-1">
            {activePdf && (
              <SheetAction
                icon={Printer}
                label={isExportingSummary ? t('chat.preparing_summary', 'Preparing Summary...') : t('workbench.print_physician', 'Print physician summary')}
                onClick={() => {
                  setMoreOpen(false);
                  setTimeout(handlePrintDoctorSummary, 250);
                }}
              />
            )}
            {onOpenExport && <SheetAction icon={Download} label={t('workbench.export_transcript', 'Export chat transcript')} onClick={() => { setMoreOpen(false); onOpenExport(); }} />}
            <SheetAction icon={Brain} label={t('workbench.memory_vault', 'Memory vault')} onClick={() => { setMoreOpen(false); onOpenMemory?.(); }} />
            <SheetAction icon={Users} label={t('workbench.caregiver_hub', 'Profile & caregivers')} onClick={() => { setMoreOpen(false); onOpenProfile?.(); }} />
            <SheetAction
              icon={Languages}
              label={uiLanguage === 'hi' ? 'Switch to English' : 'हिंदी में बदलें (Hindi)'}
              onClick={() => onSetUiLanguage?.(uiLanguage === 'hi' ? 'en' : 'hi')}
            />
            <SheetAction icon={Settings} label={t('sidebar.settings', 'Settings')} onClick={() => { setMoreOpen(false); onOpenSettings?.(); }} />
          </div>
        </Sheet>
      )}

      {/* PrintableSummary — mounted only while printing */}
      {showPrintSummary && (
        <PrintableSummary
          user={printUser || activePatient || currentUser}
          document={{ ...activePdf, collected_at: activePdf?.collected_at || printMetrics?.collected_at }}
          summary={printSummaryText || messages.filter((m) => m.sender === 'assistant').map((m) => m.text).join('\n\n')}
          metrics={printMetrics || metrics}
          specialists={messages.flatMap((m) => m.specialists || [])}
        />
      )}
    </div>
  );
}

function SheetAction({ icon: Icon, label, onClick }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="ms-tap w-full flex items-center gap-3 px-3 h-12 rounded-xl text-left text-sm text-ink-soft hover:bg-white/[0.05] hover:text-white transition"
    >
      <Icon className="w-4 h-4 text-ink-mute" />
      {label}
    </button>
  );
}
