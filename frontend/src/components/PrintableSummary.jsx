import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

// ── Sanitize emojis from text and data ─────────────────────────────────────────
function stripEmojis(text) {
  if (!text || typeof text !== 'string') return '';
  return text
    .replace(/[\u{1F600}-\u{1F64F}\u{1F300}-\u{1F5FF}\u{1F680}-\u{1F6FF}\u{1F700}-\u{1F77F}\u{1F780}-\u{1F7FF}\u{1F800}-\u{1F8FF}\u{1F900}-\u{1F9FF}\u{1FA00}-\u{1FA6F}\u{1FA70}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{2300}-\u{23FF}\u{2B50}\u{200D}\u{FE0F}]/gu, '')
    .trim();
}

// Strip LaTeX-style escapes the model sometimes emits: \( \) \% and sanitize emojis
function cleanSummary(text) {
  if (!text) return '';
  const noEmojis = stripEmojis(text);
  return noEmojis
    .replace(/\\\(/g, '')
    .replace(/\\\)/g, '')
    .replace(/\\%/g, '%');
}

export default function PrintableSummary({ user, document, summary, metrics, specialists, abnormalMetrics }) {
  // Support both field-name conventions from the backend, with email fallback
  const rawPatientName = user?.full_name || user?.name || user?.email;
  const patientName = rawPatientName ? stripEmojis(rawPatientName) : 'Not Specified';
  const patientDob  = user?.date_of_birth || user?.dob || 'Not provided';

  // Abnormal: anything whose status is truthy and not 'normal' (case-insensitive)
  // Support both m.test/m.range (LabMetrics shape) and m.name/m.reference_range
  const abnormal = (metrics || []).filter(
    (m) => m.status && m.status.toLowerCase() !== 'normal'
  );

  const now = new Date();
  const formattedDate = now.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
  const formattedTime = now.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
  const generatedAt = `${formattedDate} at ${formattedTime}`;

  const docName = stripEmojis(document?.name || document?.filename || 'Not provided');

  return (
    <div
      id="print-summary"
      style={{
        backgroundColor: '#ffffff',
        color: '#000000',
        fontFamily: '"Georgia", "Times New Roman", Times, serif',
        lineHeight: 1.5,
        padding: '0',
        margin: '0',
      }}
    >
      {/* ── Header ── */}
      <div style={{ borderBottom: '2px solid #000000', paddingBottom: '12pt', marginBottom: '16pt' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '4pt' }}>
          <h1
            style={{
              fontFamily: '"Georgia", "Times New Roman", Times, serif',
              fontSize: '18pt',
              fontWeight: 'bold',
              margin: '0 0 4pt',
              color: '#000000',
              letterSpacing: '0.02em',
            }}
          >
            CLINICAL LABORATORY SUMMARY REPORT
          </h1>
          <span style={{ fontSize: '9pt', color: '#333333', fontStyle: 'italic' }}>
            MediSkye AI
          </span>
        </div>

        <table style={{ width: '100%', fontSize: '10pt', borderCollapse: 'collapse', color: '#000000' }}>
          <tbody>
            <tr>
              <td style={{ padding: '3pt 0', width: '50%', verticalAlign: 'top' }}>
                <strong>Patient Name:</strong> {patientName}{user?.relationship ? ` (${stripEmojis(user.relationship)})` : ''}
              </td>
              <td style={{ padding: '3pt 0', width: '50%', verticalAlign: 'top' }}>
                <strong>Document / Report Name:</strong>{' '}
                <span style={{ whiteSpace: 'nowrap' }}>{docName}</span>
              </td>
            </tr>
            <tr>
              <td style={{ padding: '3pt 0', width: '50%', verticalAlign: 'top' }}>
                <strong>Date of Birth:</strong> {patientDob}
              </td>
              <td style={{ padding: '3pt 0', width: '50%', verticalAlign: 'top' }}>
                <strong>Date Generated:</strong> {generatedAt}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      {/* ── Clinical Summary ── */}
      {summary && (
        <div style={{ marginBottom: '16pt' }}>
          <h2
            style={{
              fontFamily: '"Georgia", "Times New Roman", Times, serif',
              fontSize: '13pt',
              fontWeight: 'bold',
              marginBottom: '6pt',
              color: '#000000',
            }}
          >
            Clinical Summary
          </h2>
          <div
            className="clinical-summary"
            style={{
              fontFamily: '"Georgia", "Times New Roman", Times, serif',
              fontSize: '10pt',
              lineHeight: '1.6',
              color: '#000000',
            }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cleanSummary(summary)}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* ── Abnormal Values ── */}
      {abnormal.length > 0 && (
        <div style={{ marginBottom: '16pt' }}>
          <h2
            style={{
              fontFamily: '"Georgia", "Times New Roman", Times, serif',
              fontSize: '13pt',
              fontWeight: 'bold',
              marginBottom: '6pt',
              color: '#000000',
            }}
          >
            Abnormal Values ({abnormal.length})
          </h2>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace, sans-serif',
              fontSize: '9.5pt',
              color: '#000000',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid #000000', textAlign: 'left' }}>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold' }}>Test</th>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold', fontVariantNumeric: 'tabular-nums' }}>Your Value</th>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold', fontVariantNumeric: 'tabular-nums' }}>Reference</th>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {abnormal.map((m, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #cccccc' }}>
                  <td style={{ padding: '6pt 8pt' }}>{stripEmojis(m.name || m.test)}</td>
                  <td style={{ padding: '6pt 8pt', fontVariantNumeric: 'tabular-nums' }}>
                    {stripEmojis(m.value)}{m.unit ? ` ${stripEmojis(m.unit)}` : ''}
                  </td>
                  <td style={{ padding: '6pt 8pt', fontVariantNumeric: 'tabular-nums' }}>
                    {stripEmojis(m.reference_range || m.range || '—')}
                  </td>
                  <td style={{ padding: '6pt 8pt', fontWeight: 'bold' }}>{stripEmojis(m.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── All Lab Results ── */}
      {metrics && metrics.length > 0 && (
        <div style={{ marginBottom: '16pt' }}>
          <h2
            style={{
              fontFamily: '"Georgia", "Times New Roman", Times, serif',
              fontSize: '13pt',
              fontWeight: 'bold',
              marginBottom: '6pt',
              color: '#000000',
            }}
          >
            All Lab Results
          </h2>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace, sans-serif',
              fontSize: '9.5pt',
              color: '#000000',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid #000000', textAlign: 'left' }}>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold' }}>Test</th>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold', fontVariantNumeric: 'tabular-nums' }}>Value</th>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold' }}>Unit</th>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold', fontVariantNumeric: 'tabular-nums' }}>Reference Range</th>
                <th style={{ padding: '6pt 8pt', fontWeight: 'bold' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {metrics.map((m, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #cccccc' }}>
                  <td style={{ padding: '6pt 8pt' }}>{stripEmojis(m.name || m.test)}</td>
                  <td style={{ padding: '6pt 8pt', fontVariantNumeric: 'tabular-nums' }}>{stripEmojis(m.value)}</td>
                  <td style={{ padding: '6pt 8pt' }}>{stripEmojis(m.unit || '—')}</td>
                  <td style={{ padding: '6pt 8pt', fontVariantNumeric: 'tabular-nums' }}>
                    {stripEmojis(m.reference_range || m.range || '—')}
                  </td>
                  <td style={{ padding: '6pt 8pt', fontWeight: m.status?.toLowerCase() !== 'normal' ? 'bold' : 'normal' }}>
                    {stripEmojis(m.status || 'Extracted')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Specialists ── */}
      {specialists && specialists.length > 0 && (
        <div className="specialists" style={{ marginBottom: '16pt' }}>
          <h2
            style={{
              fontFamily: '"Georgia", "Times New Roman", Times, serif',
              fontSize: '13pt',
              fontWeight: 'bold',
              marginBottom: '6pt',
              color: '#000000',
            }}
          >
            Specialists to Consider
          </h2>
          <p style={{ fontSize: '9pt', marginBottom: '8pt', color: '#000000' }}>
            Algorithmic suggestions based on detected abnormal findings. Always consult your primary care physician first.
          </p>
          <ul style={{ marginLeft: '16pt', fontSize: '10pt', color: '#000000' }}>
            {specialists.map((sp, i) => (
              <li key={i} style={{ marginBottom: '4pt' }}>
                <strong>{stripEmojis(sp.specialty)}</strong>
                {sp.matched_flags && sp.matched_flags.length > 0 && (
                  <> — for {stripEmojis(sp.matched_flags.join(', '))}</>
                )}
                {sp.name && <> ({stripEmojis(sp.name)})</>}
                {sp.contact_info && <> · {stripEmojis(sp.contact_info)}</>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Footer ── */}
      <footer
        className="print-footer"
        style={{
          marginTop: '24pt',
          paddingTop: '12pt',
          borderTop: '1px solid #000000',
          fontSize: '9pt',
          color: '#000000',
        }}
      >
        <p style={{ margin: '0 0 4pt', fontStyle: 'italic' }}>
          For informational and clinical review purposes only. Always consult a qualified physician for medical diagnosis.
          This summary is AI-generated for educational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a licensed healthcare provider.
        </p>
        <p className="generated-at" style={{ margin: 0, fontSize: '8pt', color: '#444444' }}>
          Generated by MediSkye AI on {generatedAt}
        </p>
      </footer>
    </div>
  );
}
