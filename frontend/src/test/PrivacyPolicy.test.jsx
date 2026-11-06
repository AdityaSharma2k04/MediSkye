import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { MemoryRouter } from 'react-router-dom';
import PrivacyPolicy from '../components/PrivacyPolicy';

describe('PrivacyPolicy Component', () => {
  it('renders privacy policy document with title, badge, and effective date', () => {
    render(
      <MemoryRouter>
        <PrivacyPolicy />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 1, name: /mediskye privacy policy/i })).toBeInTheDocument();
    expect(screen.getByText(/healthcare privacy & data security/i)).toBeInTheDocument();
    expect(screen.getByText(/effective date: november 2026/i)).toBeInTheDocument();
  });

  it('renders the 3 core privacy guarantee cards', () => {
    render(
      <MemoryRouter>
        <PrivacyPolicy />
      </MemoryRouter>
    );

    expect(screen.getByRole('heading', { level: 3, name: /zero model training/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /fernet encryption/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { level: 3, name: /total data sovereignty/i })).toBeInTheDocument();
  });

  it('renders mandatory sections: data collection, encryption, third-party services, and user rights', () => {
    render(
      <MemoryRouter>
        <PrivacyPolicy />
      </MemoryRouter>
    );

    // Section 1: Data Collection & Use
    expect(screen.getByText(/1\. Clinical Data Collection & Use/i)).toBeInTheDocument();
    expect(screen.getByText(/Strict AI Training Boundary:/i)).toBeInTheDocument();
    expect(screen.getByText(/Your health data is never used to train public foundation models\./i)).toBeInTheDocument();

    // Section 2: Cryptographic Data Protection & Encryption
    expect(screen.getByText(/2\. Cryptographic Data Protection & Encryption/i)).toBeInTheDocument();
    expect(screen.getByText(/Fernet Encryption at Rest/i)).toBeInTheDocument();
    expect(screen.getByText(/Secure SHA-256 Token Caching/i)).toBeInTheDocument();

    // Section 3: Third-Party Infrastructure (Google Vertex AI, Neon PostgreSQL)
    expect(screen.getByText(/3\. Third-Party Services & Infrastructure/i)).toBeInTheDocument();
    expect(screen.getByText(/Google Vertex AI:/i)).toBeInTheDocument();
    expect(screen.getByText(/Neon PostgreSQL:/i)).toBeInTheDocument();

    // Section 4: User Rights
    expect(screen.getByText(/4\. User Rights & Patient Data Sovereignty/i)).toBeInTheDocument();
    expect(screen.getByText(/Permanent Account & Data Deletion:/i)).toBeInTheDocument();

    // Section 5: Clinical Safety Disclaimer
    expect(screen.getByText(/Medical Information & Clinical Safety Disclaimer/i)).toBeInTheDocument();

    // Section 6: Contact Information
    expect(screen.getByText(/5\. Contact Information & Data Protection/i)).toBeInTheDocument();
    expect(screen.getByText('privacy@mediskye.com')).toBeInTheDocument();
    expect(screen.getByText('support@mediskye.com')).toBeInTheDocument();
  });

  it('renders navigation links to return to app or home', () => {
    render(
      <MemoryRouter>
        <PrivacyPolicy />
      </MemoryRouter>
    );

    const backLinks = screen.getAllByRole('link', { name: /back to home/i });
    expect(backLinks.length).toBeGreaterThanOrEqual(1);
    expect(backLinks[0]).toHaveAttribute('href', '/');

    const launchLink = screen.getByRole('link', { name: /launch assistant/i });
    expect(launchLink).toHaveAttribute('href', '/chat');
  });
});
