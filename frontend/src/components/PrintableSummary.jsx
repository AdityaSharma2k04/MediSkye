import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// Strip LaTeX-style escapes the model sometimes emits: \( \) \%
function cleanSummary(text) {
  if (!text) return '';
  return text
    .replace(/\\\(/g, '')
    .replace(/\\\)/g, '')
    .replace(/\\%/g, '%');
}

export default function PrintableSummary({ user, document, summary, metrics, specialists, abnormalMetrics }) {
  // Support both field-name conventions from the backend
  const patientName = user?.full_name || user?.name || 'Not provided';
  const patientDob  = user?.date_of_birth || user?.dob || 'Not provided';

  // Abnormal: anything whose status is truthy and not 'normal' (case-insensitive)
  // Support both m.test/m.range (LabMetrics shape) and m.name/m.reference_range
  const abnormal = (metrics || []).filter(
    (m) => m.status && m.status.toLowerCase() !== 'normal'
  );

  const generatedAt = new Date().toLocaleString();
  const reportDate  = new Date().toLocaleDateString(undefined, {
    year: 'numeric', month: 'long', day: 'numeric',
  });

  const docName = document?.name || document?.filename || 'Not provided';

  return (
    <div id="print-summary">

      {/* ── Header ── */}
      <div style={{ borderBottom: '2px solid #333', paddingBottom: '12pt', marginBottom: '16pt' }}>
        <h1 style={{ fontSize: '18pt', fontWeight: 'bold', margin: '0 0 8pt' }}>
          MediSkye AI — Doctor Consultation Summary
        </h1>
        <table style={{ width: '100%', fontSize: '10pt', borderCollapse: 'collapse' }}>
          <tbody>
            <tr>
              <td style={{ padding: '2pt 0' }}>
                <strong>Patient:</strong> {patientName}
              </td>
              <td style={{ padding: '2pt 0' }}>
                <strong>Date of Birth:</strong> {patientDob}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '2pt 0' }}><strong>Report Date:</strong> {reportDate}</td>
              <td style={{ padding: '2pt 0' }}><strong>Generated:</strong> {generatedAt}</td>
            </tr>
            <tr>
              <td colSpan={2} style={{ padding: '2pt 0' }}>
                <strong>Source Document:</strong>{' '}
                <span style={{ whiteSpace: 'nowrap' }}>{docName}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ── Clinical Summary ── */}
      {summary && (
        <div style={{ marginBottom: '16pt' }}>
          <h2 style={{ fontSize: '13pt', fontWeight: 'bold', marginBottom: '6pt' }}>Clinical Summary</h2>
          <div className="clinical-summary" style={{ fontSize: '10pt', lineHeight: '1.6' }}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cleanSummary(summary)}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* ── Abnormal Values ── */}
      {abnormal.length > 0 && (
        <div style={{ marginBottom: '16pt' }}>
          <h2 style={{ fontSize: '13pt', fontWeight: 'bold', marginBottom: '6pt' }}>
            Abnormal Values ({abnormal.length})
          </h2>
          <table>
            <thead>
              <tr style={{ background: '#f0f0f0' }}>
                <th>Test</th>
                <th>Your Value</th>
                <th>Reference</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {abnormal.map((m, i) => (
                <tr key={i}>
                  <td>{m.name || m.test}</td>
                  <td>{m.value}{m.unit ? ` ${m.unit}` : ''}</td>
                  <td>{m.reference_range || m.range || '—'}</td>
                  <td style={{ fontWeight: 'bold' }}>{m.status}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── All Lab Results ── */}
      {metrics && metrics.length > 0 && (
        <div style={{ marginBottom: '16pt' }}>
          <h2 style={{ fontSize: '13pt', fontWeight: 'bold', marginBottom: '6pt' }}>All Lab Results</h2>
          <table>
            <thead>
              <tr style={{ background: '#f0f0f0' }}>
                <th>Test</th>
                <th>Value</th>
                <th>Unit</th>
                <th>Reference Range</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, i) => (
                <tr key={i}>
                  <td>{m.name || m.test}</td>
                  <td>{m.value}</td>
                  <td>{m.unit || '—'}</td>
                  <td>{m.reference_range || m.range || '—'}</td>
                  <td>{m.status || 'Extracted'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Specialists ── */}
      {specialists && specialists.length > 0 && (
        <div className="specialists" style={{ marginBottom: '16pt' }}>
          <h2 style={{ fontSize: '13pt', fontWeight: 'bold', marginBottom: '6pt' }}>Specialists to Consider</h2>
          <p style={{ fontSize: '9pt', marginBottom: '8pt' }}>
            Algorithmic suggestions based on detected abnormal findings. Always consult your primary care physician first.
          </p>
          <ul style={{ marginLeft: '16pt', fontSize: '10pt' }}>
            {specialists.map((sp, i) => (
              <li key={i} style={{ marginBottom: '4pt' }}>
                <strong>{sp.specialty}</strong>
                {sp.matched_flags && sp.matched_flags.length > 0 && (
                  <> — for {sp.matched_flags.join(', ')}</>
                )}
                {sp.name && <> ({sp.name})</>}
                {sp.contact_info && <> · {sp.contact_info}</>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Footer ── */}
      <footer className="print-footer">
        <p>
          This summary is AI-generated for educational purposes only. It is not a
          substitute for professional medical advice, diagnosis, or treatment.
          Always consult a licensed healthcare provider.
        </p>
        <p className="generated-at">
          Generated by MediSkye AI on {generatedAt}
        </p>
      </footer>

    </div>
  );
}
