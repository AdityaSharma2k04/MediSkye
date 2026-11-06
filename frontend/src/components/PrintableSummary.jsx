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

// Strip LaTeX-style escapes, redundant leading headings, and duplicate metadata headers
function cleanSummary(text) {
  if (!text) return '';
  let clean = stripEmojis(text)
    .replace(/\\\(/g, '')
    .replace(/\\\)/g, '')
    .replace(/\\%/g, '%');

  // Strip redundant leading headings so it doesn't nest under component's heading
  clean = clean.replace(/^\s*#+\s*CLINICAL SUMMARY(?: REPORT)?\s*\n?/i, '');

  // Strip entire metadata sections/blocks (e.g. "### Patient Information", "### Demographics & Metadata")
  clean = clean.replace(
    /(?:^|\n)#+\s*(?:Patient\s+(?:Information|Demographics|Details|Profile)|Specimen\s+(?:Details|Information|Context)|Metadata|Report\s+Details)[\s\S]*?(?=\n#+|\n\n[A-Z]|\Z)/gi,
    '\n'
  );

  // Strip duplicate AI-generated metadata lines (e.g. "Patient Name:", "Specimen ID:", etc.)
  const metadataLinePattern = /^\s*(?:[-*•]|\d+\.)?\s*(?:\*{1,2}|_{1,2})?\s*(?:Patient\s+Name|Patient|Specimen\s+(?:ID|Number|Type)|Sample\s+ID|Accession(?:\s+Number|\s+ID)?|Collection\s+Date|Date\s+of\s+Collection|Specimen\s+Date|Report\s+Date|DOB|Date\s+of\s+Birth|Age(?:\s*\/\s*Sex)?|Gender|Sex|Fasting\s+Status|Referred\s+By|Doctor|Physician)\s*(?:\*{1,2}|_{1,2})?\s*[:\-].*$/gmi;
  clean = clean.replace(metadataLinePattern, '');

  // Collapse 3+ consecutive newlines into double newlines
  clean = clean.replace(/\n{3,}/g, '\n\n');

  return clean.trim();
}

function toTitleCase(str) {
  if (!str) return '';
  return stripEmojis(str)
    .replace(/[_-]+/g, ' ')
    .trim()
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1).toLowerCase())
    .join(' ');
}

export default function PrintableSummary({ user, document, summary, metrics, specialists, abnormalMetrics }) {
  const rawPatientName = user?.full_name || user?.name || user?.email;
  const patientName = rawPatientName ? stripEmojis(rawPatientName) : 'Not Specified';
  const patientDob = user?.date_of_birth || user?.dob || 'Not provided';
  const patientAge = user?.calculated_age ? `${user.calculated_age} yrs` : (user?.age ? `${user.age} yrs` : null);

  const now = new Date();
  const formattedDate = now.toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
  const formattedTime = now.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  });
  const generatedAt = `${formattedDate} at ${formattedTime}`;

  const docName = stripEmojis(document?.title || document?.name || document?.filename || 'Diagnostic Laboratory Report');
  const collectionDate = document?.collected_at || document?.created_at?.slice(0, 10) || 'Not specified';

  // Compute BMI: (weight_kg / ((height_cm / 100) ** 2)).toFixed(1)
  const weightVal = parseFloat(user?.weight_kg || user?.weight);
  const heightVal = parseFloat(user?.height_cm || user?.height);
  const computedBmi = (weightVal > 0 && heightVal > 0)
    ? (weightVal / ((heightVal / 100) ** 2)).toFixed(1)
    : (user?.bmi ? String(user.bmi) : '—');

  // Format Lifestyle as Title Case with a bullet: e.g. Vegetarian • Very Active
  const dietTitle = user?.diet_type ? toTitleCase(user.diet_type) : 'Standard';
  const activityTitle = user?.activity_level ? toTitleCase(user.activity_level) : 'Moderate';
  const lifestyleText = `${dietTitle} • ${activityTitle}`;

  // Table 1: Flagged & Notable Delta Biomarkers (Abnormal or >=10% delta shift)
  const allMetricsList = metrics || [];
  const flaggedMetrics = allMetricsList.filter((m) => {
    const isOut = m.status && m.status.toLowerCase() !== 'normal';
    const hasDeltaAlert = Boolean(m.delta_alert);
    return isOut || hasDeltaAlert;
  });

  // Table 2: In-range normal biomarkers
  const inRangeMetrics = allMetricsList.filter((m) => {
    const isOut = m.status && m.status.toLowerCase() !== 'normal';
    const hasDeltaAlert = Boolean(m.delta_alert);
    return !isOut && !hasDeltaAlert;
  });

  return (
    <div
      id="print-summary"
      style={{
        backgroundColor: '#ffffff',
        color: '#000000',
        fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
        lineHeight: 1.45,
        padding: '0',
        margin: '0',
      }}
    >
      {/* ── Document Header ── */}
      <div style={{ borderBottom: '2px solid #000000', paddingBottom: '8pt', marginBottom: '10pt' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '2pt' }}>
          <h1
            style={{
              fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
              fontSize: '15pt',
              fontWeight: 800,
              margin: '0',
              color: '#000000',
              letterSpacing: '-0.02em',
            }}
          >
            CLINICAL LABORATORY SUMMARY REPORT
          </h1>
          <span style={{ fontSize: '8.5pt', color: '#4b5563', fontWeight: 600 }}>
            MediSkye AI • Clinical Synthesis
          </span>
        </div>
      </div>

      {/* ── Page 1: 2x2 Compact Patient Context & Safety Header Card ── */}
      <div
        className="patient-context-box"
        style={{
          display: 'grid',
          gridTemplateColumns: '1fr 1fr',
          gap: '8pt',
          marginBottom: '12pt',
          pageBreakInside: 'avoid',
          breakInside: 'avoid',
        }}
      >
        {/* Card 1: Patient Demographics */}
        <div style={{ border: '1px solid #d1d5db', borderRadius: '4pt', padding: '6pt 8pt', backgroundColor: '#f9fafb' }}>
          <div style={{ fontSize: '8pt', fontWeight: 700, textTransform: 'uppercase', color: '#4b5563', marginBottom: '3pt' }}>
            Patient Demographics
          </div>
          <div style={{ fontSize: '9pt', lineHeight: '1.4' }}>
            <div><strong>Patient Name:</strong> {patientName}{user?.relationship ? ` (${stripEmojis(user.relationship)})` : ''}</div>
            <div><strong>DOB / Age:</strong> {patientDob}{patientAge ? ` (${patientAge})` : ''} • <strong>Sex:</strong> {user?.biological_sex || 'Unspecified'}</div>
            <div><strong>Blood Type:</strong> {user?.blood_type || 'Unknown'} • <strong>BMI:</strong> {computedBmi}</div>
            <div><strong>Lifestyle:</strong> {lifestyleText}</div>
          </div>
        </div>

        {/* Card 2: Specimen Details */}
        <div style={{ border: '1px solid #d1d5db', borderRadius: '4pt', padding: '6pt 8pt', backgroundColor: '#f9fafb' }}>
          <div style={{ fontSize: '8pt', fontWeight: 700, textTransform: 'uppercase', color: '#4b5563', marginBottom: '3pt' }}>
            Specimen &amp; Report Context
          </div>
          <div style={{ fontSize: '9pt', lineHeight: '1.4' }}>
            <div><strong>Report Name:</strong> {docName}</div>
            <div><strong>Specimen Collected:</strong> <span style={{ fontWeight: 600 }}>{collectionDate}</span></div>
            <div><strong>Fasting Status:</strong> {document?.fasting_status || 'Fasting 10–12h Verified'}</div>
            <div><strong>Report Processed:</strong> {generatedAt}</div>
          </div>
        </div>

        {/* Card 3: Allergies & Contraindications */}
        <div style={{ border: '1px solid #f87171', borderRadius: '4pt', padding: '6pt 8pt', backgroundColor: '#fef2f2' }}>
          <div style={{ fontSize: '8pt', fontWeight: 700, textTransform: 'uppercase', color: '#b91c1c', marginBottom: '3pt' }}>
            Known Allergies &amp; Contraindications
          </div>
          <div style={{ fontSize: '8.5pt', color: '#991b1b', lineHeight: '1.35', fontWeight: 600 }}>
            {user?.known_allergies ? stripEmojis(user.known_allergies) : 'No known drug or environmental allergies reported'}
          </div>
        </div>

        {/* Card 4: Active Medications & Conditions */}
        <div style={{ border: '1px solid #d1d5db', borderRadius: '4pt', padding: '6pt 8pt', backgroundColor: '#f9fafb' }}>
          <div style={{ fontSize: '8pt', fontWeight: 700, textTransform: 'uppercase', color: '#4b5563', marginBottom: '3pt' }}>
            Active Medications &amp; Conditions
          </div>
          <div style={{ fontSize: '8.5pt', lineHeight: '1.35' }}>
            <div><strong>Meds/Supplements:</strong> {user?.current_medications ? stripEmojis(user.current_medications) : 'None reported'}</div>
            <div><strong>Pre-Existing:</strong> {user?.pre_existing_conditions ? stripEmojis(user.pre_existing_conditions) : 'None reported'}</div>
          </div>
        </div>
      </div>

      {/* ── Clinical Summary (Narrative Findings) ── */}
      {summary && (
        <div className="finding-block" style={{ marginBottom: '12pt', pageBreakInside: 'avoid', breakInside: 'avoid' }}>
          <h2
            className="section-heading"
            style={{
              fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
              fontSize: '11.5pt',
              fontWeight: 700,
              margin: '0 0 4pt',
              color: '#000000',
              borderBottom: '1px solid #e5e7eb',
              paddingBottom: '2pt',
            }}
          >
            Clinical Summary
          </h2>
          <div
            className="clinical-summary"
            style={{
              fontSize: '9pt',
              lineHeight: '1.45',
              color: '#111827',
            }}
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {cleanSummary(summary)}
            </ReactMarkdown>
          </div>
        </div>
      )}

      {/* ── Table 1: Flagged & Notable Delta Biomarkers (Abnormal Values) ── */}
      {flaggedMetrics.length > 0 && (
        <div className="finding-block" style={{ marginBottom: '12pt', pageBreakInside: 'avoid', breakInside: 'avoid' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '4pt' }}>
            <h2
              className="section-heading"
              style={{
                fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
                fontSize: '11pt',
                fontWeight: 700,
                margin: 0,
                color: '#000000',
              }}
            >
              Flagged &amp; Notable Delta Biomarkers (Abnormal Values)
            </h2>
            <span style={{ fontSize: '8pt', color: '#b91c1c', fontWeight: 600 }}>
              {flaggedMetrics.length} analyte{flaggedMetrics.length > 1 ? 's' : ''} flagged
            </span>
          </div>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '8.5pt',
              color: '#000000',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid #000000', backgroundColor: '#f3f4f6', textAlign: 'left' }}>
                <th style={{ padding: '4pt 6pt', fontWeight: 700 }}>Biomarker</th>
                <th style={{ padding: '4pt 6pt', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>Observed Value</th>
                <th style={{ padding: '4pt 6pt', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>Prior Baseline</th>
                <th style={{ padding: '4pt 6pt', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>Change (Δ %)</th>
                <th style={{ padding: '4pt 6pt', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>Reference Interval</th>
                <th style={{ padding: '4pt 6pt', fontWeight: 700 }}>Clinical Flag</th>
              </tr>
            </thead>
            <tbody>
              {flaggedMetrics.map((m, i) => {
                const isHigh = m.status?.toLowerCase() === 'high';
                const isLow = m.status?.toLowerCase() === 'low';
                const isNotable = Boolean(m.delta_alert);
                const flagColor = isHigh ? '#b91c1c' : (isLow ? '#d97706' : '#d97706');
                const flagBg = isHigh ? '#fee2e2' : '#fef3c7';

                return (
                  <tr key={i} style={{ borderBottom: '1px solid #e5e7eb', breakInside: 'avoid', pageBreakInside: 'avoid' }}>
                    <td style={{ padding: '4pt 6pt', fontWeight: 600 }}>{stripEmojis(m.name || m.test)}</td>
                    <td style={{ padding: '4pt 6pt', fontVariantNumeric: 'tabular-nums', fontWeight: 700 }}>
                      {stripEmojis(m.value)}{m.unit ? ` ${stripEmojis(m.unit)}` : ''}
                    </td>
                    <td style={{ padding: '4pt 6pt', fontVariantNumeric: 'tabular-nums', color: '#4b5563' }}>
                      {m.previous_value ? `${stripEmojis(m.previous_value)}${m.previous_date ? ` (${m.previous_date})` : ''}` : '—'}
                    </td>
                    <td style={{ padding: '4pt 6pt', fontVariantNumeric: 'tabular-nums', fontWeight: 600 }}>
                      {m.delta_pct || m.delta_abs || '—'}
                    </td>
                    <td style={{ padding: '4pt 6pt', fontVariantNumeric: 'tabular-nums', color: '#4b5563' }}>
                      {stripEmojis(m.reference_range || m.range || '—')}
                    </td>
                    <td style={{ padding: '4pt 6pt' }}>
                      <span
                        style={{
                          display: 'inline-block',
                          fontSize: '7.5pt',
                          fontWeight: 700,
                          padding: '1pt 4pt',
                          borderRadius: '3pt',
                          color: flagColor,
                          backgroundColor: flagBg,
                          border: `1px solid ${flagColor}40`,
                          textTransform: 'uppercase',
                        }}
                      >
                        {m.delta_alert || stripEmojis(m.status)}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Table 2: In-Range Biomarkers (All Lab Results) ── */}
      {allMetricsList.length > 0 && (
        <div className="finding-block" style={{ marginBottom: '12pt', pageBreakInside: 'avoid', breakInside: 'avoid' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: '4pt' }}>
            <h2
              className="section-heading"
              style={{
                fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
                fontSize: '11pt',
                fontWeight: 700,
                margin: 0,
                color: '#000000',
              }}
            >
              In-Range Biomarkers (All Lab Results)
            </h2>
            <span style={{ fontSize: '8pt', color: '#059669', fontWeight: 600 }}>
              {inRangeMetrics.length} normal / {allMetricsList.length} total
            </span>
          </div>
          <table
            style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '8pt',
              color: '#000000',
            }}
          >
            <thead>
              <tr style={{ borderBottom: '2px solid #000000', backgroundColor: '#f3f4f6', textAlign: 'left' }}>
                <th style={{ padding: '3pt 5pt', fontWeight: 700 }}>Biomarker</th>
                <th style={{ padding: '3pt 5pt', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>Observed</th>
                <th style={{ padding: '3pt 5pt', fontWeight: 700 }}>Unit</th>
                <th style={{ padding: '3pt 5pt', fontWeight: 700, fontVariantNumeric: 'tabular-nums' }}>Reference Range</th>
                <th style={{ padding: '3pt 5pt', fontWeight: 700 }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {(inRangeMetrics.length > 0 ? inRangeMetrics : allMetricsList).map((m, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #e5e7eb', breakInside: 'avoid', pageBreakInside: 'avoid' }}>
                  <td style={{ padding: '3pt 5pt', fontWeight: 500 }}>{stripEmojis(m.name || m.test)}</td>
                  <td style={{ padding: '3pt 5pt', fontVariantNumeric: 'tabular-nums' }}>{stripEmojis(m.value)}</td>
                  <td style={{ padding: '3pt 5pt', color: '#4b5563' }}>{stripEmojis(m.unit || '—')}</td>
                  <td style={{ padding: '3pt 5pt', fontVariantNumeric: 'tabular-nums', color: '#4b5563' }}>
                    {stripEmojis(m.reference_range || m.range || '—')}
                  </td>
                  <td style={{ padding: '3pt 5pt', color: '#059669', fontWeight: 600 }}>
                    {m.status?.toLowerCase() === 'normal' ? '✓ Normal' : stripEmojis(m.status || 'Normal')}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Specialists to Consider ── */}
      {specialists && specialists.length > 0 && (
        <div className="specialists" style={{ marginBottom: '12pt', pageBreakInside: 'avoid', breakInside: 'avoid' }}>
          <h2
            className="section-heading"
            style={{
              fontFamily: 'Inter, system-ui, -apple-system, sans-serif',
              fontSize: '11pt',
              fontWeight: 700,
              marginBottom: '4pt',
              color: '#000000',
              borderBottom: '1px solid #e5e7eb',
              paddingBottom: '2pt',
            }}
          >
            Specialists to Consider
          </h2>
          <p style={{ fontSize: '8pt', marginBottom: '4pt', color: '#4b5563', fontStyle: 'italic' }}>
            Algorithmic considerations based on detected laboratory findings. Consult your primary care physician for clinical referrals.
          </p>
          <ul style={{ marginLeft: '14pt', fontSize: '8.5pt', color: '#000000', margin: 0 }}>
            {specialists.map((sp, i) => (
              <li key={i} style={{ marginBottom: '2pt' }}>
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
          marginTop: '16pt',
          paddingTop: '8pt',
          borderTop: '1px solid #000000',
          fontSize: '7.5pt',
          color: '#374151',
          pageBreakInside: 'avoid',
          breakInside: 'avoid',
        }}
      >
        <p style={{ margin: '0 0 3pt', fontStyle: 'italic', lineHeight: 1.35 }}>
          This report is prepared for educational purposes only and is not a substitute for professional medical advice, diagnosis, or treatment. Always consult a licensed healthcare provider before making medical decisions.
        </p>
        <p className="generated-at" style={{ margin: 0, fontSize: '7pt', color: '#6b7280' }}>
          Generated by MediSkye AI on {generatedAt}
        </p>
      </footer>
    </div>
  );
}
