import { Link } from "react-router-dom";
import SEO from "../components/SEO";

export default function Security() {
  return (
    <div className="legal-page">
      <SEO
        title="Security"
        description="How CaseRaft for Claude protects your Clio data: encrypted credentials, read-only tools, audit logging of every access, and one-click revocation."
        path="/security"
      />
      <div className="legal-container">
        <Link to="/connect" className="legal-back">&larr; Back to CaseRaft for Claude</Link>

        <h1>Security and Confidentiality</h1>
        <p className="legal-effective">
          Plain-language answers about how CaseRaft for Claude handles your
          Clio data. Last updated: July 24, 2026.
        </p>

        <section>
          <h2>The short version</h2>
          <p>
            CaseRaft for Claude is designed for confidentiality. The
            connector is read-only, your credentials are encrypted and never
            displayed, every access is logged, your case data is not kept
            after a request finishes, and you can disconnect it at any time
            with one button. The rest of this page explains each of those
            claims.
          </p>
        </section>

        <section>
          <h2>Where do my Clio credentials live?</h2>
          <p>
            When you sign in, Clio gives CaseRaft an access token, not your
            password. We never see or store your Clio password. That token is
            encrypted at rest using Fernet symmetric encryption before it
            touches our database, and it is never displayed to you, to
            Claude, or to anyone at CaseRaft. The tokens Claude uses to talk
            to CaseRaft are stored only as one-way hashes, so even a copy of
            our database would not contain a usable token.
          </p>
        </section>

        <section>
          <h2>What can Claude actually do with my data?</h2>
          <p>
            Read only. Every tool in the connector reads from Clio; none of
            them can create, modify, or delete anything in your account.
            There is no way to ask Claude to change a matter, move money, or
            edit a contact through CaseRaft, because no such tool exists on
            our side. If we ever add write features, they will be off by
            default and opt-in per user.
          </p>
        </section>

        <section>
          <h2>Is anything kept after Claude gets its answer?</h2>
          <p>
            No. When Claude asks a question, CaseRaft fetches the relevant
            data from Clio, computes the answer, returns it, and discards the
            data. Your matters, contacts, and billing records are not
            retained on our servers beyond the lifetime of that single
            request. What we do keep is the audit trail described below.
          </p>
        </section>

        <section>
          <h2>Who can see what Claude asked for?</h2>
          <p>
            You can. Every tool call is written to an audit log: which
            account, which tool, and when. This is the same audit logging
            that already covers report generation in CaseRaft. If you ever
            want a copy of your access history, email us and we will send it.
          </p>
        </section>

        <section>
          <h2>Does Anthropic train on my conversations?</h2>
          <p>
            By default, Anthropic does not train its models on conversations
            from paid Claude plans. Training settings are controlled in your
            Claude account, not in CaseRaft, so we encourage you to review
            Anthropic's current privacy documentation and your own Claude
            settings. CaseRaft never sends your data to Anthropic on its own;
            data only moves when you ask Claude a question.
          </p>
        </section>

        <section>
          <h2>How do I disconnect it?</h2>
          <p>
            Two independent ways, and either one works on its own:
          </p>
          <ul>
            <li>
              <strong>In CaseRaft:</strong> open Billing and Subscription in
              the app and click Revoke access on the Claude Connector card.
              Claude's access ends immediately; the next thing it sees is an
              authorization error.
            </li>
            <li>
              <strong>In Clio:</strong> you can also revoke CaseRaft's own
              access to Clio from your Clio account's connected app
              settings. That cuts off everything CaseRaft can read,
              including reports.
            </li>
          </ul>
          <p>
            Reconnecting later is the same three-step setup, so there is no
            penalty for turning it off while you evaluate it.
          </p>
        </section>

        <section>
          <h2>What we do not promise</h2>
          <p>
            No vendor can honestly guarantee perfect security, and we will
            not pretend to. What we can say is that the connector is designed
            for confidentiality from the start: read-only tools, encrypted
            credentials, hashed tokens, per-request data handling, and a
            complete audit trail. If you have a question this page does not
            answer, ask us before you connect.
          </p>
        </section>

        <section>
          <h2>Questions</h2>
          <p>
            Email <a href="mailto:info@caseraft.com">info@caseraft.com</a>.
            A person reads it.
          </p>
        </section>

        <div className="legal-footer">
          <p>
            Case Raft integrates with Clio Manage through the official Clio
            API. Clio is a trademark of Themis Solutions Inc. Case Raft is an
            independent product and is not affiliated with, endorsed by, or
            sponsored by Clio. Claude is a product of Anthropic, PBC; Case
            Raft is not affiliated with Anthropic.
          </p>
        </div>
      </div>
    </div>
  );
}
