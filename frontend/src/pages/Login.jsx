import { useState } from "react";
import { Link } from "react-router-dom";
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
          <div className="landing-nav-links">
            <a href="#pricing" className="landing-nav-link">Pricing</a>
            <a href="#compare" className="landing-nav-link">Compare Plans</a>
            <a href={getLoginUrl()} className="btn btn-accent btn-small">
              Sign In
            </a>
          </div>
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
          <a href="#pricing" className="btn btn-accent btn-large">
            View Plans &amp; Pricing
          </a>
          <p className="hero-note">Powered by Clio Manage · OAuth 2.0 secure</p>
        </div>
      </section>

      {/* ── How It Works ── */}
      <section className="how-it-works">
        <div className="section-inner">
          <h2>How It Works</h2>
          <div className="steps-row">
            <div className="step">
              <div className="step-number">1</div>
              <h3>Choose a Plan</h3>
              <p>Pick the plan that fits your firm. Solo, Team, or Firm — all with 50% off your first month.</p>
            </div>
            <div className="step-arrow">&#8594;</div>
            <div className="step">
              <div className="step-number">2</div>
              <h3>Connect Clio</h3>
              <p>Authorize with one click. Case Raft reads your matters, contacts, and billing data securely.</p>
            </div>
            <div className="step-arrow">&#8594;</div>
            <div className="step">
              <div className="step-number">3</div>
              <h3>Generate Reports</h3>
              <p>Browse your cases, hit Generate, and download professionally formatted PDFs in seconds.</p>
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

      {/* ── Pricing ── */}
      <section className="landing-pricing" id="pricing">
        <div className="section-inner">
          <div className="landing-pricing-badge">🎉 50% off your first month</div>
          <h2>Simple, Transparent Pricing</h2>
          <p className="landing-pricing-sub">
            Professional Clio reporting tools for every firm size. No contracts. Cancel anytime.
          </p>
          <div className="landing-pricing-grid">
            <div className="landing-price-card">
              <h3>Solo</h3>
              <div className="landing-price-amount"><span className="landing-price-dollar">$</span>29<span className="landing-price-period">/mo</span></div>
              <p className="landing-price-desc">For solo practitioners</p>
              <ul>
                <li>Case summary reports</li>
                <li>PDF export &amp; download</li>
                <li>Report history</li>
                <li>Basic firm reports</li>
                <li>1 user</li>
              </ul>
              <a href={getLoginUrl()} className="btn btn-primary btn-large">Get Started</a>
            </div>
            <div className="landing-price-card landing-price-card-featured">
              <div className="landing-price-popular">Most Popular</div>
              <h3>Team</h3>
              <div className="landing-price-amount"><span className="landing-price-dollar">$</span>79<span className="landing-price-period">/mo</span></div>
              <p className="landing-price-desc">For small to mid-size firms</p>
              <ul>
                <li>Everything in Solo</li>
                <li>Full firm productivity reports</li>
                <li>Batch report generation</li>
                <li>Revenue &amp; utilization analytics</li>
                <li>CSV export (QuickBooks / Xero)</li>
                <li>Up to 5 users</li>
              </ul>
              <a href={getLoginUrl()} className="btn btn-accent btn-large">Get Started</a>
            </div>
            <div className="landing-price-card">
              <h3>Firm</h3>
              <div className="landing-price-amount"><span className="landing-price-dollar">$</span>149<span className="landing-price-period">/mo</span></div>
              <p className="landing-price-desc">For larger practices</p>
              <ul>
                <li>Everything in Team</li>
                <li>Unlimited batch reports</li>
                <li>Custom report sections</li>
                <li>AR aging analysis</li>
                <li>Priority support</li>
                <li>Unlimited users</li>
              </ul>
              <a href={getLoginUrl()} className="btn btn-primary btn-large">Get Started</a>
            </div>
          </div>
          <p className="landing-pricing-compare"><a href="#compare">Compare all features &rarr;</a></p>
        </div>
      </section>

      {/* ── Compare Plans ── */}
      <section className="landing-compare" id="compare">
        <div className="section-inner">
          <h2>Compare Plans</h2>
          <p className="landing-compare-sub">
            A detailed breakdown of every feature across all plans.
          </p>
          <div className="landing-compare-table-wrapper">
            <table className="landing-compare-table">
              <thead>
                <tr>
                  <th></th>
                  <th>Solo <span>$29/mo</span></th>
                  <th className="landing-compare-featured">Team <span>$79/mo</span></th>
                  <th>Firm <span>$149/mo</span></th>
                </tr>
              </thead>
              <tbody>
                <tr className="landing-compare-category"><td colSpan={4}>Reporting</td></tr>
                <tr><td>Case summary reports</td><td>✓</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>
                <tr><td>PDF export &amp; download</td><td>✓</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>
                <tr><td>Report download history</td><td>✓</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>
                <tr><td>Firm productivity reports</td><td>Basic</td><td className="landing-compare-featured">Full</td><td>Full</td></tr>
                <tr><td>Batch report generation</td><td>—</td><td className="landing-compare-featured">Up to 20</td><td>Unlimited</td></tr>
                <tr><td>Custom report sections</td><td>—</td><td className="landing-compare-featured">—</td><td>✓</td></tr>

                <tr className="landing-compare-category"><td colSpan={4}>Analytics</td></tr>
                <tr><td>Collected revenue reports</td><td>—</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>
                <tr><td>Realization &amp; utilization rates</td><td>—</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>
                <tr><td>Write-off tracking</td><td>—</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>
                <tr><td>AR aging analysis</td><td>—</td><td className="landing-compare-featured">—</td><td>✓</td></tr>

                <tr className="landing-compare-category"><td colSpan={4}>Export &amp; Integration</td></tr>
                <tr><td>Clio Manage integration</td><td>✓</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>
                <tr><td>CSV export (QuickBooks / Xero)</td><td>—</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>

                <tr className="landing-compare-category"><td colSpan={4}>Users &amp; Support</td></tr>
                <tr><td>Users included</td><td>1</td><td className="landing-compare-featured">Up to 5</td><td>Unlimited</td></tr>
                <tr><td>Email support</td><td>✓</td><td className="landing-compare-featured">✓</td><td>✓</td></tr>
                <tr><td>Priority support</td><td>—</td><td className="landing-compare-featured">—</td><td>✓</td></tr>
              </tbody>
            </table>
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
          <p>Choose a plan, connect your Clio Manage account, and generate your first report in under a minute.</p>
          <a href="#pricing" className="btn btn-accent btn-large">
            Get Started
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
            <div className="footer-col">
              <h4>Legal</h4>
              <Link to="/privacy-policy">Privacy Policy</Link>
              <Link to="/terms-of-service">Terms of Service</Link>
            </div>
          </div>
          <div className="footer-bottom">
            <p>&copy; {new Date().getFullYear()} Case Raft. All rights reserved.</p>
            <div className="footer-bottom-links">
              <Link to="/privacy-policy">Privacy Policy</Link>
              <span className="footer-divider">|</span>
              <Link to="/terms-of-service">Terms of Service</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
