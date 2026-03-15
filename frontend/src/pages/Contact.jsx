import { useState } from "react";
import { submitContact } from "../services/api";

export default function Contact() {
  const [form, setForm] = useState({ name: "", email: "", firm_name: "", message: "" });
  const [status, setStatus] = useState(null); // null | "sending" | "success" | "error"
  const [errorMsg, setErrorMsg] = useState("");

  const handleChange = (e) => {
    setForm({ ...form, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus("sending");
    setErrorMsg("");

    try {
      await submitContact(form);
      setStatus("success");
      setForm({ name: "", email: "", firm_name: "", message: "" });
    } catch (err) {
      setStatus("error");
      setErrorMsg(err.response?.data?.error || "Something went wrong. Please try again.");
    }
  };

  return (
    <div className="contact-page">
      <div className="contact-page-inner">
        <div className="contact-info">
          <h1>Get in Touch</h1>
          <p className="contact-info-sub">
            Have questions about CaseRaft or need help choosing the right plan?
            We'd love to hear from you.
          </p>

          <div className="contact-details">
            <div className="contact-detail-item">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
              <span>shobinn@eclarx.com</span>
            </div>
            <div className="contact-detail-item">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z" />
                <circle cx="12" cy="10" r="3" />
              </svg>
              <span>New York, NY</span>
            </div>
          </div>

          <div className="contact-response">
            <strong>Typical response time</strong>
            <span>Within 24 hours on business days</span>
          </div>
        </div>

        <div className="contact-form-wrapper">
          {status === "success" ? (
            <div className="contact-success">
              <div className="contact-success-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                  <polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <h3>Message Sent!</h3>
              <p>Thank you for reaching out. We'll get back to you within 24 hours.</p>
              <button className="btn btn-accent" onClick={() => setStatus(null)}>
                Send Another Message
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="contact-form">
              <div className="contact-form-row">
                <div className="contact-field">
                  <label htmlFor="name">Name *</label>
                  <input
                    type="text" id="name" name="name"
                    value={form.name} onChange={handleChange}
                    placeholder="Your full name"
                    required
                  />
                </div>
                <div className="contact-field">
                  <label htmlFor="email">Email *</label>
                  <input
                    type="email" id="email" name="email"
                    value={form.email} onChange={handleChange}
                    placeholder="you@firm.com"
                    required
                  />
                </div>
              </div>
              <div className="contact-field">
                <label htmlFor="firm_name">Firm Name</label>
                <input
                  type="text" id="firm_name" name="firm_name"
                  value={form.firm_name} onChange={handleChange}
                  placeholder="Your law firm (optional)"
                />
              </div>
              <div className="contact-field">
                <label htmlFor="message">Message *</label>
                <textarea
                  id="message" name="message" rows={5}
                  value={form.message} onChange={handleChange}
                  placeholder="How can we help?"
                  required
                />
              </div>
              {status === "error" && (
                <div className="contact-error">{errorMsg}</div>
              )}
              <button
                type="submit"
                className="btn btn-accent btn-large contact-submit"
                disabled={status === "sending"}
              >
                {status === "sending" ? "Sending..." : "Send Message"}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
