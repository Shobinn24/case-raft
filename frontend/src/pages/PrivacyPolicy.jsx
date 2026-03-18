import { Link } from "react-router-dom";

export default function PrivacyPolicy() {
  return (
    <div className="legal-page">
      <div className="legal-container">
        <Link to="/" className="legal-back">&larr; Back to Home</Link>

        <h1>Privacy Policy</h1>
        <p className="legal-effective">Effective Date: March 17, 2026</p>

        <section>
          <h2>1. Introduction</h2>
          <p>
            Case Raft ("we," "us," or "our") provides a reporting and analytics
            platform for law firms that integrates with Clio Manage. This Privacy
            Policy explains how we collect, use, and protect your information
            when you use our service at caseraft.com (the "Service").
          </p>
        </section>

        <section>
          <h2>2. Information We Collect</h2>

          <h3>Account Information</h3>
          <p>
            When you sign in through Clio, we receive your name, email address,
            and Clio user ID via OAuth 2.0. We store this information to
            identify your account and manage your subscription.
          </p>

          <h3>Clio Data (Read-Only Access)</h3>
          <p>
            Our integration with Clio Manage requests <strong>read-only</strong>{" "}
            access to your firm's data, including matters, contacts, billing
            entries, trust account balances, and custom fields. We do not modify,
            create, or delete any data in your Clio account.
          </p>

          <h3>Report Data</h3>
          <p>
            When you generate a report, we temporarily retrieve data from Clio's
            API to produce your PDF. We store a record of report generation
            (report type, date, and matter reference) in your report history. The
            generated PDF content is not permanently stored on our servers.
          </p>

          <h3>Payment Information</h3>
          <p>
            Subscription payments are processed through Stripe. We do not store
            your credit card number or full payment details. Stripe handles all
            payment data in compliance with PCI-DSS standards. We only retain
            your Stripe customer ID and subscription status.
          </p>

          <h3>Usage Data</h3>
          <p>
            We may collect basic usage information such as pages visited, reports
            generated, and login timestamps to improve the Service.
          </p>
        </section>

        <section>
          <h2>3. How We Use Your Information</h2>
          <ul>
            <li>To authenticate your identity and maintain your account</li>
            <li>To generate reports by retrieving data from Clio on your behalf</li>
            <li>To process subscription payments through Stripe</li>
            <li>To maintain your report download history</li>
            <li>To provide customer support</li>
            <li>To improve and maintain the Service</li>
          </ul>
        </section>

        <section>
          <h2>4. Data Sharing</h2>
          <p>We do not sell your personal information. We share data only with:</p>
          <ul>
            <li>
              <strong>Stripe</strong> — for payment processing
            </li>
            <li>
              <strong>Clio</strong> — we interact with Clio's API on your behalf
              using the OAuth tokens you authorize
            </li>
            <li>
              <strong>Legal requirements</strong> — if required by law,
              subpoena, or legal process
            </li>
          </ul>
        </section>

        <section>
          <h2>5. Data Security</h2>
          <p>
            We protect your data using industry-standard measures including
            encrypted connections (HTTPS/TLS), secure OAuth 2.0 token handling,
            and access controls. Clio API tokens are stored securely and are
            never exposed to third parties.
          </p>
        </section>

        <section>
          <h2>6. Data Retention</h2>
          <p>
            We retain your account information for as long as your account is
            active. Report history records are kept to provide your download
            history. If you delete your account, we will remove your personal
            information and Clio tokens from our systems within 30 days.
          </p>
        </section>

        <section>
          <h2>7. Cookies</h2>
          <p>
            We use essential cookies to maintain your login session. We do not
            use advertising or third-party tracking cookies.
          </p>
        </section>

        <section>
          <h2>8. Your Rights</h2>
          <p>You have the right to:</p>
          <ul>
            <li>Access the personal information we hold about you</li>
            <li>Request correction of inaccurate information</li>
            <li>Request deletion of your account and associated data</li>
            <li>
              Revoke Clio access at any time through your Clio account settings
            </li>
            <li>Cancel your subscription at any time</li>
          </ul>
        </section>

        <section>
          <h2>9. Children's Privacy</h2>
          <p>
            The Service is not intended for use by individuals under 18 years of
            age. We do not knowingly collect information from minors.
          </p>
        </section>

        <section>
          <h2>10. Changes to This Policy</h2>
          <p>
            We may update this Privacy Policy from time to time. We will notify
            you of material changes by posting the updated policy on this page
            with a revised effective date.
          </p>
        </section>

        <section>
          <h2>11. Contact Us</h2>
          <p>
            If you have questions about this Privacy Policy or your data, please
            contact us at{" "}
            <a href="mailto:support@caseraft.com">support@caseraft.com</a>.
          </p>
        </section>

        <div className="legal-footer">
          <p>&copy; {new Date().getFullYear()} Case Raft. All rights reserved.</p>
        </div>
      </div>
    </div>
  );
}
