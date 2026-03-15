import { useState } from "react";
import { getLoginUrl, submitContact } from "../services/api";
import logo from "../assets/caseraftlogo.jpg";

function LandingContactForm() {
  const [form, setForm] = useState({ name: "", email: "", firm_name: "", message: "" });
  const [status, setStatus] = useState(null);

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value });

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus("sending");
    try {
      await submitContact(form);
      setStatus("success");
      setForm({ name: "", email: "", firm_name: "", message: "" });
    } catch {
      setStatus("error");
    }
  };

  if (status === "success") {
    return (
      <div className="landing-contact-success">
        <h3>Message Sent!</h3>
        <p>We'll get back to you within 24 hours.</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="landing-contact-form">
      <div className="landing-contact-row">
        <input type="text" name="name" value={form.name} onChange={handleChange} placeholder="Your name *" required />
        <input type="email" name="email" value={form.email} onChange={handleChange} placeholder="Email address *" required />
      </div>
      <input type="text" name="firm_name" value={form.firm_name} onChange={handleChange} placeholder="Firm name (optional)" />
      <textarea name="message" rows={4} value={form.message} onChange={handleChange} placeholder="How can we help? *" required />
      {status === "error" && <p className="landing-contact-error">Something went wrong. Please try again.</p>}
      <button type="submit" className="btn btn-accent btn-large" disabled={status === "sending"}>
        {status === "sending" ? "Sending..." : "Send Message"}
      </button>
    </form>
  );
}

export default function Login() {
  return (
    <div className="landing">
      {/* ── Navigation ── */}
      <nav className="landing-nav">
        <div className="landing-nav-inner">
          <div className="landing-nav-brand">
            <img src={logo} alt="Case Raft" className="landing-logo" />
          </div>
          <a href={getLoginUrl()} className="btn btn-accent btn-small">
            Sign In
          </a>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="hero">
        <div className="hero-inner">
          <div className="hero-badge">Built for Clio Manage</div>
          <h1>From Clio Data to Court-Ready Reports in 60 Seconds.</h1>
          <p className="hero-sub">
            Stop manually compiling matter summaries. Case Raft connects to your
            Clio Manage account to generate comprehensive, professional PDF
            reports instantly.
          </p>
          <a href={getLoginUrl()} className="btn btn-accent btn-large">
            Connect Clio Manage
          </a>
          <p className="hero-note">OAuth 2.0 — we never see your password</p>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="how-it-works">
        <div className="section-inner">
          <h2>How It Works</h2>
          <div className="steps-row">
            <div className="step">
              <div className="step-number">1</div>
              <h3>Connect Clio</h3>
              <p>Authorize with one click. Case Raft reads your matters, contacts, and billing data securely.</p>
            </div>
            <div className="step-arrow">&#8594;</div>
            <div className="step">
              <div className="step-number">2</div>
              <h3>Select &amp; Generate</h3>
              <p>Browse your cases, pick the ones you need, and hit Generate. Reports build in seconds.</p>
            </div>
            <div className="step-arrow">&#8594;</div>
            <div className="step">
              <div className="step-number">3</div>
              <h3>Download PDF</h3>
              <p>Get a professionally formatted PDF with matter details, billing summaries, and contacts.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Three Pillars ── */}
      <section className="pillars">
        <div className="section-inner">
          <h2>Built by Operators, for Operators</h2>
          <div className="pillars-grid">
            <div className="pillar-card">
              <div className="pillar-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                  <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                </svg>
              </div>
              <h3>Deep Integration</h3>
              <p>Pulls everything — from opposing counsel contacts to real-time billing balances — directly from your Clio Matters.</p>
            </div>
            <div className="pillar-card">
              <div className="pillar-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
                </svg>
              </div>
              <h3>Operator-Speed</h3>
              <p>Built for the busy partner. Browse cases, click Generate, and get your PDF. No configuration required.</p>
            </div>
            <div className="pillar-card">
              <div className="pillar-icon">
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              </div>
              <h3>Audit-Ready History</h3>
              <p>A permanent vault of every report you've ever generated. Re-download any report in one click.</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── What's In a Report ── */}
      <section className="report-preview">
        <div className="section-inner">
          <h2>What's Inside Every Report</h2>
          <div className="report-sections-grid">
            <div className="report-section-item">
              <h4>Matter Overview</h4>
              <p>Case number, description, status, practice area, responsible attorney, key dates</p>
            </div>
            <div className="report-section-item">
              <h4>Client Details</h4>
              <p>Name, contact info, addresses, company affiliations, date of birth</p>
            </div>
            <div className="report-section-item">
              <h4>Opposing Parties</h4>
              <p>Opposing counsel, judges, clerks — every related contact on the matter</p>
            </div>
            <div className="report-section-item">
              <h4>Financial Summary</h4>
              <p>Total billed vs. paid, outstanding balances, invoice history with line items</p>
            </div>
            <div className="report-section-item">
              <h4>Time Entries</h4>
              <p>Billable hours, rates, descriptions — every activity logged to the matter</p>
            </div>
            <div className="report-section-item">
              <h4>Firm Productivity</h4>
              <p>Employee hours, revenue by attorney, firm-wide billing summaries by date range</p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Trust / Security ── */}
      <section className="trust">
        <div className="section-inner">
          <h2>Your Data Stays in Clio</h2>
          <p className="trust-sub">
            Case Raft never stores your case data. We use OAuth 2.0 to
            read from Clio on demand and generate reports in real time. Your
            credentials never touch our servers.
          </p>
          <div className="trust-grid">
            <div className="trust-item">
              <strong>OAuth 2.0</strong>
              <span>We never see your Clio password. Authorization is handled entirely by Clio.</span>
            </div>
            <div className="trust-item">
              <strong>Read-Only Access</strong>
              <span>Case Raft only reads data. We cannot modify, delete, or create anything in your Clio account.</span>
            </div>
            <div className="trust-item">
              <strong>No Data Storage</strong>
              <span>Case and client data is fetched fresh for each report. Nothing is cached or stored on our servers.</span>
            </div>
          </div>
        </div>
      </section>

      {/* ── Contact ── */}
      <section className="landing-contact">
        <div className="section-inner">
          <h2>Questions? Let's Talk.</h2>
          <p className="landing-contact-sub">
            Whether you're evaluating CaseRaft for your firm or need help getting started, drop us a line.
          </p>
          <LandingContactForm />
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="cta">
        <div className="section-inner">
          <h2>Ready to streamline your case reporting?</h2>
          <p>Connect your Clio Manage account and generate your first report in under a minute.</p>
          <a href={getLoginUrl()} className="btn btn-accent btn-large">
            Get Started with Clio
          </a>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="landing-footer">
        <div className="footer-inner">
          <div className="footer-brand">
            <img src={logo} alt="Case Raft" className="footer-logo" />
          </div>
          <div className="footer-links">
            <div className="footer-col">
              <h4>Product</h4>
              <span>Case Reports</span>
              <span>Firm Productivity</span>
              <span>Report History</span>
            </div>
            <div className="footer-col">
              <h4>Security</h4>
              <span>OAuth 2.0</span>
              <span>Read-Only Access</span>
              <span>No Data Storage</span>
            </div>
            <div className="footer-col">
              <h4>Integration</h4>
              <span>Clio Manage</span>
              <span>PDF Export</span>
            </div>
          </div>
          <div className="footer-bottom">
            <p>&copy; {new Date().getFullYear()} Case Raft. All rights reserved.</p>
            <p className="footer-tagline">Professional case reports, built by operators.</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
