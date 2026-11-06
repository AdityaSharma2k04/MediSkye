import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  Shield,
  Lock,
  Server,
  UserCheck,
  FileText,
  Mail,
  Database,
  Cpu,
  ArrowLeft,
  CheckCircle2,
  AlertCircle,
  ExternalLink,
} from 'lucide-react';

export default function PrivacyPolicy() {
  // Ensure dark mode obsidian palette
  useEffect(() => {
    document.documentElement.classList.add('dark');
    try {
      localStorage.setItem('theme', 'dark');
    } catch (_) {}
    window.scrollTo(0, 0);
  }, []);

  const hasToken = typeof window !== 'undefined' && Boolean(localStorage.getItem('token'));
  const backDestination = hasToken ? '/chat' : '/';
  const backLabel = hasToken ? 'Back to App' : 'Back to Home';

  return (
    <div className="min-h-screen bg-[#07090e] text-slate-100 font-sans selection:bg-cyan-500/25 selection:text-cyan-200 relative overflow-x-hidden">
      {/* Background radial glows */}
      <div
        className="pointer-events-none fixed top-0 left-1/2 -translate-x-1/2 w-[1000px] h-[500px] bg-gradient-to-b from-cyan-500/10 via-blue-500/5 to-transparent blur-[140px] opacity-75"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none fixed bottom-0 right-0 w-[600px] h-[600px] bg-gradient-to-tl from-cyan-900/10 via-transparent to-transparent blur-[160px]"
        aria-hidden="true"
      />

      {/* Top Navigation */}
      <header className="sticky top-0 z-40 bg-[#07090e]/85 backdrop-blur-md border-b border-white/[0.08] px-4 sm:px-8 py-3.5 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link
            to={backDestination}
            className="p-2 rounded-xl text-slate-400 hover:text-white hover:bg-white/[0.06] transition-colors flex items-center gap-1.5 text-xs font-medium"
            aria-label={backLabel}
          >
            <ArrowLeft className="w-4 h-4" />
            <span className="hidden sm:inline">{backLabel}</span>
          </Link>
          <div className="h-4 w-px bg-white/10 hidden sm:block" />
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-cyan-500 to-blue-500 flex items-center justify-center shadow-md shadow-cyan-500/20">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="text-slate-950">
                <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
              </svg>
            </div>
            <span className="font-semibold text-sm tracking-tight text-white">MediSkye</span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <Link
            to="/chat"
            className="px-3.5 py-1.5 text-xs font-semibold rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 transition shadow-sm shadow-cyan-500/20"
          >
            Launch Assistant
          </Link>
        </div>
      </header>

      {/* Document Hero */}
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 sm:py-16 relative z-10">
        <div className="space-y-4 text-center sm:text-left border-b border-white/[0.08] pb-10">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] font-semibold uppercase tracking-wider bg-cyan-500/10 text-cyan-300 border border-cyan-500/20">
            <Shield className="w-3.5 h-3.5 text-cyan-400" />
            Healthcare Privacy &amp; Data Security
          </div>
          <h1 className="text-3xl sm:text-4xl lg:text-5xl font-bold tracking-tight text-white">
            MediSkye Privacy Policy
          </h1>
          <p className="text-sm sm:text-base text-slate-400 max-w-2xl leading-relaxed">
            Your clinical data and medical history belong exclusively to you. Read how MediSkye uses state-of-the-art encryption, zero public AI training retention, and strict access controls to safeguard your health information.
          </p>
          <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-2 font-mono">
            <span>Effective Date: November 2026</span>
            <span>•</span>
            <span>Version: 2.0.0</span>
            <span>•</span>
            <span className="text-emerald-400 flex items-center gap-1 font-sans">
              <CheckCircle2 className="w-3.5 h-3.5" /> Fernet-Encrypted PHI Storage &amp; Strict Per-User Isolation
            </span>
          </div>
        </div>

        {/* 3 Core Guarantees Cards */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 my-10">
          <div className="p-5 rounded-2xl bg-[#0e131b] border border-white/[0.08] space-y-2">
            <div className="w-9 h-9 rounded-xl bg-cyan-500/10 text-cyan-400 flex items-center justify-center border border-cyan-500/20">
              <Cpu className="w-4 h-4" />
            </div>
            <h3 className="font-semibold text-sm text-white">Zero Model Training</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Your uploaded lab reports and questions are never used to train, retrain, or improve public AI foundation models.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-[#0e131b] border border-white/[0.08] space-y-2">
            <div className="w-9 h-9 rounded-xl bg-emerald-500/10 text-emerald-400 flex items-center justify-center border border-emerald-500/20">
              <Lock className="w-4 h-4" />
            </div>
            <h3 className="font-semibold text-sm text-white">Fernet Encryption</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Medical profiles and vitals are encrypted at rest using Fernet symmetric encryption with SHA-256 token caching.
            </p>
          </div>

          <div className="p-5 rounded-2xl bg-[#0e131b] border border-white/[0.08] space-y-2">
            <div className="w-9 h-9 rounded-xl bg-purple-500/10 text-purple-400 flex items-center justify-center border border-purple-500/20">
              <UserCheck className="w-4 h-4" />
            </div>
            <h3 className="font-semibold text-sm text-white">Total Data Sovereignty</h3>
            <p className="text-xs text-slate-400 leading-relaxed">
              Export your full transcript and clinical biomarkers anytime, or permanently wipe your account and memory with one click.
            </p>
          </div>
        </div>

        {/* Policy Body */}
        <div className="space-y-12 text-sm leading-relaxed text-slate-300">
          {/* Section 1: Data Collection & Use */}
          <section className="space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-lg border-b border-white/[0.08] pb-2">
              <FileText className="w-5 h-5 text-cyan-400" />
              <h2>1. Clinical Data Collection &amp; Use</h2>
            </div>
            <p>
              MediSkye collects only the information necessary to provide you with empathetic, understandable clinical explanations of diagnostic reports:
            </p>
            <ul className="list-disc list-inside space-y-2 pl-2 text-slate-300">
              <li>
                <strong className="text-white">Account Information:</strong> Your authenticated email address, authentication provider (Email/Password or Google OAuth), optional display name, and language preferences.
              </li>
              <li>
                <strong className="text-white">Diagnostic Documents:</strong> Uploaded text-based medical reports (such as Complete Blood Counts, Comprehensive Metabolic Panels, Lipid Panels, or pathology summaries) processed to extract structured biomarkers and reference ranges.
              </li>
              <li>
                <strong className="text-white">Clinical Inquiries &amp; Consultations:</strong> Questions you ask regarding your medical reports, symptom descriptions, and educational conversational threads.
              </li>
              <li>
                <strong className="text-white">Patient Memory &amp; Health Profile (Optional):</strong> Remembered medical facts (such as existing conditions, current medications, allergies, or lifestyle habits) that you explicitly choose to save to provide context across visits.
              </li>
            </ul>
            <div className="p-4 rounded-xl bg-cyan-950/30 border border-cyan-500/30 text-cyan-200 text-xs flex items-start gap-3">
              <Shield className="w-4 h-4 text-cyan-400 shrink-0 mt-0.5" />
              <div>
                <strong className="text-white font-semibold">Strict AI Training Boundary: </strong>
                All clinical data processed by MediSkye is isolated to your active session. We do NOT sell, license, or provide your Protected Health Information (PHI) to third-party data brokers or AI model trainers. Your health data is never used to train public foundation models.
              </div>
            </div>
          </section>

          {/* Section 2: Data Encryption & Security */}
          <section className="space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-lg border-b border-white/[0.08] pb-2">
              <Lock className="w-5 h-5 text-cyan-400" />
              <h2>2. Cryptographic Data Protection &amp; Encryption</h2>
            </div>
            <p>
              We implement industry-standard cryptographic primitives to ensure confidentiality, integrity, and privacy of your records:
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 rounded-xl bg-[#0e131b] border border-white/[0.08] space-y-1.5">
                <div className="text-xs font-semibold text-white flex items-center gap-2">
                  <Database className="w-4 h-4 text-emerald-400" />
                  Fernet Encryption at Rest
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Medical profiles, clinical vitals, remembered conditions, and sensitive patient records are encrypted at rest using authenticated symmetric Fernet encryption (AES-128 in CBC mode with HMAC SHA-256).
                </p>
              </div>

              <div className="p-4 rounded-xl bg-[#0e131b] border border-white/[0.08] space-y-1.5">
                <div className="text-xs font-semibold text-white flex items-center gap-2">
                  <Lock className="w-4 h-4 text-cyan-400" />
                  Secure SHA-256 Token Caching
                </div>
                <p className="text-xs text-slate-400 leading-relaxed">
                  Session authentication and API credentials use one-way SHA-256 cryptographic hashing and secure in-memory caching to eliminate plain-text credential persistence.
                </p>
              </div>
            </div>
            <p className="text-xs text-slate-400">
              All data transmitted between your browser and MediSkye servers is protected by modern Transport Layer Security (TLS 1.3 / HTTPS) with strict HTTP Strict Transport Security (HSTS) headers.
            </p>
          </section>

          {/* Section 3: Third-Party Infrastructure */}
          <section className="space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-lg border-b border-white/[0.08] pb-2">
              <Server className="w-5 h-5 text-cyan-400" />
              <h2>3. Third-Party Services &amp; Infrastructure</h2>
            </div>
            <p>
              MediSkye operates on enterprise-tier infrastructure providers that adhere to rigorous security and compliance frameworks:
            </p>
            <ul className="list-disc list-inside space-y-2 pl-2 text-slate-300">
              <li>
                <strong className="text-white">Google Vertex AI:</strong> Provides real-time multimodal inference and clinical language understanding via dedicated enterprise endpoints. Vertex AI terms explicitly prohibit using customer prompts or responses to train Google models.
              </li>
              <li>
                <strong className="text-white">Neon PostgreSQL:</strong> Provides secure, cloud-native transactional database hosting with automated point-in-time encryption and isolated patient tenant partitioning.
              </li>
              <li>
                <strong className="text-white">Firebase Authentication:</strong> Provides decentralized identity federation, password hashing (scrypt), and secure token issuance.
              </li>
            </ul>
          </section>

          {/* Section 4: User Rights & Data Sovereignty */}
          <section className="space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-lg border-b border-white/[0.08] pb-2">
              <UserCheck className="w-5 h-5 text-cyan-400" />
              <h2>4. User Rights &amp; Patient Data Sovereignty</h2>
            </div>
            <p>
              You maintain total control over your medical records and conversation history:
            </p>
            <div className="space-y-3">
              <div className="p-3.5 rounded-xl border border-white/[0.08] bg-[#0e131b] flex items-start gap-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-white text-xs block">Export Clinical Data:</strong>
                  <span className="text-xs text-slate-400">
                    Export your complete consultation transcript, extracted lab metrics, and doctor summaries anytime in structured JSON format or printable consultation PDF via the Export button in Chat or Settings.
                  </span>
                </div>
              </div>

              <div className="p-3.5 rounded-xl border border-white/[0.08] bg-[#0e131b] flex items-start gap-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-white text-xs block">Clear Remembered Facts:</strong>
                  <span className="text-xs text-slate-400">
                    Review and selectively delete individual clinical facts, or purge all cross-session memory immediately from the Patient Memory tab in Settings.
                  </span>
                </div>
              </div>

              <div className="p-3.5 rounded-xl border border-white/[0.08] bg-[#0e131b] flex items-start gap-3">
                <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                <div>
                  <strong className="text-white text-xs block">Permanent Account &amp; Data Deletion:</strong>
                  <span className="text-xs text-slate-400">
                    You can delete your MediSkye account at any time in Settings. Deletion is instantaneous and cascades permanently across all uploaded documents, conversation threads, dependent profiles, and encrypted database records.
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* Section 5: Clinical Boundaries Disclaimer */}
          <section className="space-y-3 p-5 rounded-2xl bg-amber-500/10 border border-amber-500/25 text-amber-200">
            <div className="flex items-center gap-2 font-semibold text-sm text-white">
              <AlertCircle className="w-4 h-4 text-amber-400" />
              Medical Information &amp; Clinical Safety Disclaimer
            </div>
            <p className="text-xs leading-relaxed text-amber-100/90">
              MediSkye is an AI-powered educational assistant designed to make complex laboratory values, medical summaries, and clinical jargon understandable. MediSkye does not provide medical diagnoses, prescribe treatments, or replace the relationship between you and your physician. In an emergency, always contact your local emergency services (e.g., 911 or 112) or seek care at the nearest urgent care facility immediately.
            </p>
          </section>

          {/* Section 6: Contact & Support */}
          <section className="space-y-4">
            <div className="flex items-center gap-2.5 text-white font-semibold text-lg border-b border-white/[0.08] pb-2">
              <Mail className="w-5 h-5 text-cyan-400" />
              <h2>5. Contact Information &amp; Data Protection</h2>
            </div>
            <p>
              If you have any questions, concerns, or requests regarding this Privacy Policy or how your clinical health data is handled, please contact our team:
            </p>
            <div className="p-4 rounded-xl bg-[#0e131b] border border-white/[0.08] space-y-2 text-xs">
              <div>
                <span className="text-slate-400">Privacy &amp; Data Protection Officer: </span>
                <a href="mailto:privacy@mediskye.com" className="text-cyan-400 hover:underline">
                  privacy@mediskye.com
                </a>
              </div>
              <div>
                <span className="text-slate-400">General Support &amp; Clinical Inquiries: </span>
                <a href="mailto:support@mediskye.com" className="text-cyan-400 hover:underline">
                  support@mediskye.com
                </a>
              </div>
            </div>
          </section>
        </div>

        {/* Document Footer */}
        <div className="mt-16 pt-8 border-t border-white/[0.08] flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-slate-500">
          <div>&copy; 2026 MediSkye AI. All rights reserved.</div>
          <div className="flex items-center gap-4">
            <Link to={backDestination} className="text-slate-400 hover:text-white transition-colors">
              {backLabel}
            </Link>
            <span>•</span>
            <Link to="/login" className="text-slate-400 hover:text-white transition-colors">
              Sign In
            </Link>
            <span>•</span>
            <Link to="/register" className="text-slate-400 hover:text-white transition-colors">
              Register
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
}
