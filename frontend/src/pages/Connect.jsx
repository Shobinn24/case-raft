import { useState } from "react";
import { Link } from "react-router-dom";
import { getLoginUrl } from "../services/api";
import SEO from "../components/SEO";
import logo from "../assets/caseraftlogo.jpg";

const CONNECTOR_URL = "https://mcp.caseraft.com/mcp";

const TOOLS = [
  {
    name: "Check your connection",
    desc: "Confirms which Clio account is linked, so you always know whose data Claude is looking at.",
  },
  {
    name: "Browse your matters",
    desc: "List open, pending, or closed matters by client, status, or practice area.",
  },
  {
    name: "Pull up a matter file",
    desc: "Full detail on any matter: related contacts, opposing parties, and a billing summary.",
  },
  {
    name: "Find contacts",
    desc: "Search clients, opposing counsel, judges, and clerks, and pull their details.",
  },
  {
    name: "Firm productivity",
    desc: "Hours by employee, billable split, realization and collection rates for any date range.",
  },
  {
    name: "Outstanding revenue",
    desc: "Collected versus outstanding receivables by practice area, with aging buckets.",
  },
  {
    name: "Trust balances",
    desc: "Trust account balances against your minimums, with per-client shortfalls flagged.",
  },
  {
    name: "Daily digest",
    desc: "Today's tasks, calendar, unpaid bills, and recent activity in one answer.",
  },
];

const PROMPTS = [
  {
    name: "Morning digest",
    desc: '"Give me my morning digest" gets you today\'s schedule, tasks, and anything overdue before your first cup of coffee.',
  },
  {
    name: "Status update email",
    desc: "Claude drafts a client-ready status update from the actual activity on a matter. You review and send.",
  },
  {
    name: "Intake summary",
    desc: "Turn a new contact and matter into a clean intake summary you can drop into your file.",
  },
];

function CopyUrlBox() {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(CONNECTOR_URL);
    } catch {
      // Fallback for older browsers or non-secure contexts
      const el = document.createElement("textarea");
      el.value = CONNECTOR_URL;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      document.body.removeChild(el);
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="connect-url-box">
      <code>{CONNECTOR_URL}</code>
      <button type="button" className="btn btn-accent btn-small" onClick={handleCopy}>
        {copied ? "Copied!" : "Copy"}
      </button>
    </div>
  );
}

export default function Connect({ standalone = false }) {
  const page = (
    <div className="landing connect-page">
      <SEO
        title="Connect Clio to Claude"
        description="CaseRaft for Claude connects your Clio Manage account to Claude in one click. Ask about matters, billing, and trust balances in plain English. Read-only and audit-logged."
        path="/connect"
      />

      {standalone && (
        <nav className="landing-nav">
          <div className="landing-nav-inner">
            <div className="landing-nav-brand">
              <Link to="/">
                <img src={logo} alt="Case Raft" className="landing-logo" />
              </Link>
            </div>
            <div className="landing-nav-links">
              <Link to="/security" className="landing-nav-link">Security</Link>
              <a href={getLoginUrl()} className="btn btn-accent btn-small">
                Sign In
              </a>
            </div>
          </div>
        </nav>
      )}

      {/* ── Hero ── */}
      <section className="hero connect-hero">
        <div className="hero-inner">
          <div className="hero-badge">CaseRaft for Claude</div>
          <h1>Connect your Clio to Claude in one click.</h1>
          <p className="hero-sub">
            Ask Claude about your matters, contacts, billing, and trust
            balances in plain English. CaseRaft is the bridge: nothing to
            install, nothing to host, no API keys to manage. If you can
            paste a link, you can set this up.
          </p>
          <a href="#connect-steps" className="btn btn-accent btn-large">
            Set It Up in Three Steps
          </a>
          <p className="hero-note">
            Read-only access &middot; Every access logged &middot; Revoke anytime
          </p>
        </div>
      </section>

      {/* ── Three Steps ── */}
      <section className="how-it-works" id="connect-steps">
        <div className="section-inner">
          <h2>Three Steps, About Two Minutes</h2>
          <div className="connect-steps">
            <div className="connect-step">
              <div className="connect-step-text">
                <div className="step-number">1</div>
                <h3>Copy the CaseRaft connector address</h3>
                <p>
                  This is the address Claude uses to reach your CaseRaft
                  account. Copy it now; you will paste it in the next step.
                </p>
                <CopyUrlBox />
              </div>
              <div className="connect-step-visual" aria-hidden="true">
                <span>Screenshot: the connector address, copied</span>
              </div>
            </div>

            <div className="connect-step">
              <div className="connect-step-text">
                <div className="step-number">2</div>
                <h3>Paste it into Claude</h3>
                <p>
                  In Claude, open <strong>Settings</strong>, choose{" "}
                  <strong>Connectors</strong>, then click{" "}
                  <strong>Add custom connector</strong> and paste the address.
                </p>
                <p className="connect-step-note">
                  This works on claude.ai in your browser, in the Claude
                  Desktop app, and on the Claude mobile app. Custom
                  connectors are available on every Claude plan.
                </p>
              </div>
              <div className="connect-step-visual" aria-hidden="true">
                <span>Screenshot: Claude Settings, Connectors, Add custom connector</span>
              </div>
            </div>

            <div className="connect-step">
              <div className="connect-step-text">
                <div className="step-number">3</div>
                <h3>Click Connect and sign in with Clio</h3>
                <p>
                  Claude sends you to CaseRaft, where you sign in with your
                  Clio account the same way you already do. Approve once and
                  you are connected. You never type your Clio password into
                  Claude or into CaseRaft.
                </p>
              </div>
              <div className="connect-step-visual" aria-hidden="true">
                <span>Screenshot: the CaseRaft approval page</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── What You Get ── */}
      <section className="report-preview">
        <div className="section-inner">
          <h2>What You Can Ask For</h2>
          <p className="connect-section-sub">
            Eight tools, all read-only. Claude picks the right one from your
            plain-English question.
          </p>
          <div className="report-sections-grid">
            {TOOLS.map((tool) => (
              <div className="report-section-item" key={tool.name}>
                <h4>{tool.name}</h4>
                <p>{tool.desc}</p>
              </div>
            ))}
          </div>

          <h2 className="connect-prompts-heading">Three Starter Prompts, Built In</h2>
          <p className="connect-section-sub">
            These ship with the connector, so your first conversation already
            knows what a lawyer needs.
          </p>
          <div className="connect-prompts-grid">
            {PROMPTS.map((prompt) => (
              <div className="pillar-card" key={prompt.name}>
                <h3>{prompt.name}</h3>
                <p>{prompt.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── Trust Strip ── */}
      <section className="trust">
        <div className="section-inner">
          <h2>Built for Client Confidentiality</h2>
          <p className="trust-sub">
            You are trusting this with client data, so the boring parts are
            the important parts.
          </p>
          <div className="trust-grid">
            <div className="trust-item">
              <strong>Read-Only</strong>
              <span>
                Every tool can only read. Nothing in the connector can
                create, change, or delete anything in your Clio account.
              </span>
            </div>
            <div className="trust-item">
              <strong>Encrypted</strong>
              <span>
                Your Clio credentials are encrypted at rest and are never
                shown to Claude, to Anthropic, or to anyone at CaseRaft.
              </span>
            </div>
            <div className="trust-item">
              <strong>Every Access Logged</strong>
              <span>
                Each tool call is written to an audit log: who, what, and
                when. Ask us for your log anytime.
              </span>
            </div>
            <div className="trust-item">
              <strong>Revoke Anytime</strong>
              <span>
                One button in your CaseRaft settings disconnects Claude
                immediately. You stay in control.
              </span>
            </div>
          </div>
          <p className="connect-trust-more">
            <Link to="/security">Read the full security overview &rarr;</Link>
          </p>
        </div>
      </section>

      {/* ── CTA ── */}
      <section className="cta">
        <div className="section-inner">
          <h2>Already a CaseRaft customer?</h2>
          <p>
            The Claude connector is included on every paid CaseRaft plan at
            no extra cost. Sign in, then follow the three steps above.
          </p>
          <a href={getLoginUrl()} className="btn btn-accent btn-large">
            Sign In with Clio
          </a>
          <p className="hero-note">
            New here? <Link to="/">See plans and pricing</Link>
          </p>
        </div>
      </section>

      {/* ── Footer / compliance ── */}
      <footer className="landing-footer connect-footer">
        <div className="footer-inner">
          <div className="footer-bottom">
            <p>&copy; {new Date().getFullYear()} Case Raft. All rights reserved.</p>
            <p className="footer-disclaimer">
              Case Raft integrates with Clio Manage through the official Clio
              API. Clio is a trademark of Themis Solutions Inc. Case Raft is
              an independent product and is not affiliated with, endorsed by,
              or sponsored by Clio. Claude is a product of Anthropic, PBC;
              Case Raft is not affiliated with Anthropic.
            </p>
            <div className="footer-bottom-links">
              <Link to="/security">Security</Link>
              <span className="footer-divider">|</span>
              <Link to="/privacy-policy">Privacy Policy</Link>
              <span className="footer-divider">|</span>
              <Link to="/terms-of-service">Terms of Service</Link>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );

  return page;
}
