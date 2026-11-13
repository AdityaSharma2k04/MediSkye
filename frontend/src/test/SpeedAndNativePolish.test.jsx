import { describe, it, expect, vi, beforeEach } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { warmBackendConnection } from '../services/api';
import ChatMessage, { stripAbnormalFlags } from '../components/ChatMessage';
import Workbench from '../components/workbench/Workbench';

describe('Frontend Speed & UX Polish', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('warmBackendConnection makes a non-blocking fetch to /health', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(() => Promise.resolve({ ok: true }));
    warmBackendConnection();
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining('/health'),
      expect.objectContaining({
        method: 'GET',
        mode: 'cors',
        credentials: 'omit',
      })
    );
    fetchSpy.mockRestore();
  });

  it('stripAbnormalFlags removes trailing or complete abnormal_flags json blocks', () => {
    const textWithFlags = 'Your blood sugar is slightly elevated.\n```json\n{"abnormal_flags": ["GLUCOSE_HIGH"]}\n```';
    expect(stripAbnormalFlags(textWithFlags)).toBe('Your blood sugar is slightly elevated.');
  });

  it('ChatMessage renders assistant response and handles action buttons', () => {
    const msg = {
      id: 'msg-1',
      sender: 'assistant',
      text: 'Hemoglobin is in the normal range.',
      timestamp: '10:00 AM',
    };
    render(<ChatMessage message={msg} />);
    expect(screen.getByText(/Hemoglobin is in the normal range/i)).toBeInTheDocument();
  });

  it('Workbench displays subtle offline status pill when isOnline is false', () => {
    render(
      <Workbench
        isDesktop={true}
        isMobile={false}
        toggleSidebar={() => {}}
        currentUser={{ id: 'u1', full_name: 'Test Patient' }}
        dependents={[]}
        selectedPatientId="self"
        onSelectPatient={() => {}}
        onOpenDependents={() => {}}
        activePatient={{ id: 'u1', full_name: 'Test Patient' }}
        patientName="Test Patient"
        reportCounts={{}}
        messages={[]}
        isGenerating={false}
        loadingHistory={false}
        onRegenerate={() => {}}
        onSendMessage={() => {}}
        onTrySampleReport={() => {}}
        onAttachFile={() => {}}
        onStopGeneration={() => {}}
        chatInputRef={{ current: null }}
        composerDocuments={[]}
        onDetachDocument={() => {}}
        onRemoveFile={() => {}}
        activePdf={null}
        documentId={null}
        attachedDocuments={[]}
        metrics={[]}
        metricsLoading={false}
        metricsError={null}
        onReloadMetrics={() => {}}
        ensureMetrics={() => Promise.resolve([])}
        trends={{}}
        inspectorOpen={false}
        onToggleInspector={() => {}}
        inspectorTab="metrics"
        onInspectorTabChange={() => {}}
        metricsFilter="all"
        onMetricsFilterChange={() => {}}
        metricsSearch=""
        onMetricsSearchChange={() => {}}
        highlightKey={null}
        onFocusMetric={() => {}}
        onAskAbout={() => {}}
        viewMode="chat"
        onViewModeChange={() => {}}
        uploadState={null}
        onDismissUpload={() => {}}
        uploadError={null}
        onDismissUploadError={() => {}}
        isExportingSummary={false}
        printSummaryText=""
        onExportSummary={() => {}}
        onOpenExport={() => {}}
        onOpenPalette={() => {}}
        onOpenSettings={() => {}}
        onOpenMemory={() => {}}
        onOpenProfile={() => {}}
        isOnline={false}
      />
    );

    expect(screen.getByText(/Offline — viewing cached data/i)).toBeInTheDocument();
  });
});

