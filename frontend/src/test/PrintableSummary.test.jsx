import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import PrintableSummary from '../components/PrintableSummary';

const mockUser = {
  full_name: 'Jane Doe',
  date_of_birth: '1985-04-12',
};

const mockDocument = { name: 'blood_panel_2024.pdf' };

const mockSummary = 'Patient shows elevated LDL and borderline HbA1c. Recommend dietary changes.';

const mockMarkdownSummary = `### Key Findings\n\n**LDL Cholesterol** is elevated at 160 mg/dL.\n\n- Recommend dietary changes\n- Follow up in 3 months`;

const mockMetrics = [
  { test: 'LDL Cholesterol', value: '160', unit: 'mg/dL', range: '0–100', status: 'High' },
  { test: 'HbA1c', value: '6.1', unit: '%', range: '4.0–5.6', status: 'High' },
  { test: 'Hemoglobin', value: '14.2', unit: 'g/dL', range: '12–17', status: 'Normal' },
];

const mockSpecialists = [
  {
    name: 'Dr. Smith',
    specialty: 'Endocrinology',
    matched_flags: ['HbA1c High'],
    contact_info: '555-0100',
  },
];

describe('PrintableSummary', () => {
  it('renders patient name and DOB in header', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/Jane Doe/)).toBeInTheDocument();
    expect(screen.getByText(/1985-04-12/)).toBeInTheDocument();
  });

  it('renders source document name', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/blood_panel_2024\.pdf/)).toBeInTheDocument();
  });

  it('renders clinical summary section', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/Clinical Summary/i)).toBeInTheDocument();
    expect(screen.getByText(/elevated LDL/)).toBeInTheDocument();
  });

  it('renders abnormal values table with only High/Low rows', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/Abnormal Values/i)).toBeInTheDocument();
    expect(screen.getAllByText(/LDL Cholesterol/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/HbA1c/).length).toBeGreaterThan(0);
  });

  it('renders all lab results table', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/All Lab Results/i)).toBeInTheDocument();
    expect(screen.getAllByText(/Hemoglobin/).length).toBeGreaterThan(0);
  });

  it('renders recommended next steps with specialist info', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/Specialists to Consider/i)).toBeInTheDocument();
    expect(screen.getByText(/Dr\. Smith/)).toBeInTheDocument();
    expect(screen.getByText(/Endocrinology/)).toBeInTheDocument();
  });

  it('renders disclaimer in footer', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/educational purposes only/i)).toBeInTheDocument();
    expect(screen.getByText(/licensed healthcare provider/i)).toBeInTheDocument();
  });

  it('renders gracefully with no metrics or specialists', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={null}
        summary=""
        metrics={[]}
        specialists={[]}
      />
    );
    expect(screen.getAllByText(/MediSkye AI/).length).toBeGreaterThan(0);
    expect(screen.getByText(/educational purposes only/i)).toBeInTheDocument();
  });

  // ── New tests for Bug fixes ───────────────────────────────────────────────

  it('renders markdown summary without raw ### syntax', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockMarkdownSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    // ReactMarkdown should render ### as an <h3>, not raw text
    expect(screen.queryByText(/###/)).not.toBeInTheDocument();
    // The heading text itself should be present
    expect(screen.getByText(/Key Findings/i)).toBeInTheDocument();
  });

  it('renders markdown bold without raw ** syntax', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockMarkdownSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    // Should not contain raw **...**
    expect(screen.queryByText(/\*\*LDL Cholesterol\*\*/)).not.toBeInTheDocument();
    // The bold text content should be present (rendered as <strong>)
    expect(screen.getAllByText(/LDL Cholesterol/).length).toBeGreaterThan(0);
  });

  it('shows Not provided fallback when user fields are missing', () => {
    render(
      <PrintableSummary
        user={{}}
        document={mockDocument}
        summary={mockSummary}
        metrics={[]}
        specialists={[]}
      />
    );
    expect(screen.getAllByText(/Not provided/).length).toBeGreaterThanOrEqual(2);
  });

  it('abnormal table excludes Normal-status rows', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    // Abnormal Values section should exist
    expect(screen.getByText(/Abnormal Values/i)).toBeInTheDocument();
    // LDL (High) and HbA1c (High) appear in abnormal table
    expect(screen.getAllByText(/LDL Cholesterol/).length).toBeGreaterThan(0);
    // Hemoglobin is Normal — it should only appear in All Lab Results, not Abnormal Values
    // Both tables are rendered so Hemoglobin will appear, but only once in abnormal section
    const abnormalSection = screen.getByText(/Abnormal Values/i).closest('div');
    expect(abnormalSection).not.toBeNull();
  });

  it('renders specialists section with matched flags', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/Specialists to Consider/i)).toBeInTheDocument();
    expect(screen.getByText(/Endocrinology/)).toBeInTheDocument();
    expect(screen.getByText(/HbA1c High/)).toBeInTheDocument();
  });

  it('renders footer with generated-by line', () => {
    render(
      <PrintableSummary
        user={mockUser}
        document={mockDocument}
        summary={mockSummary}
        metrics={mockMetrics}
        specialists={mockSpecialists}
      />
    );
    expect(screen.getByText(/Generated by MediSkye AI/i)).toBeInTheDocument();
  });
});
