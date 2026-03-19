import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { getCase, generateReport, getReportDownloadUrl } from "../services/api";
import SEO from "../components/SEO";

export default function CaseDetail() {
  const { caseId } = useParams();
  const [caseData, setCaseData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    getCase(caseId)
      .then((res) => setCaseData(res.data.data))
      .catch((err) => setError(err.response?.data?.error || "Failed to load case"))
      .finally(() => setLoading(false));
  }, [caseId]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      const res = await generateReport(parseInt(caseId));
      setGeneratedReport(res.data.report);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <div className="loading">Loading case...</div>;
  if (error && !caseData) return <div className="error">{error}</div>;

  const c = caseData;

  return (
    <section>
      <SEO title={c.display_number ? `Case ${c.display_number}` : "Case Detail"} path={`/cases/${caseId}`} />
      <Link to="/cases" className="back-link">&larr; Back to Cases</Link>

      <div className="detail-header">
        <h2>{c.display_number}</h2>
        <span className={`status-badge status-${c.status?.toLowerCase()}`}>
          {c.status}
        </span>
      </div>

      <div className="detail-grid">
        <div className="detail-section">
          <h3>Case Information</h3>
          <table className="detail-table">
            <tbody>
              <tr><td>Description</td><td>{c.description || "—"}</td></tr>
              <tr><td>Practice Area</td><td>{c.practice_area?.name || "—"}</td></tr>
              <tr><td>Matter Stage</td><td>{c.matter_stage?.name || "—"}</td></tr>
              <tr><td>Billing Method</td><td>{c.billing_method || "—"}</td></tr>
              <tr><td>Billable</td><td>{c.billable ? "Yes" : "No"}</td></tr>
            </tbody>
          </table>
        </div>

        <div className="detail-section">
          <h3>Key Dates</h3>
          <table className="detail-table">
            <tbody>
              <tr><td>Opened</td><td>{c.open_date || "—"}</td></tr>
              <tr><td>Pending</td><td>{c.pending_date || "—"}</td></tr>
              <tr><td>Closed</td><td>{c.close_date || "—"}</td></tr>
            </tbody>
          </table>
        </div>

        <div className="detail-section">
          <h3>Attorneys</h3>
          <table className="detail-table">
            <tbody>
              <tr><td>Responsible</td><td>{c.responsible_attorney?.name || "—"}</td></tr>
              <tr><td>Originating</td><td>{c.originating_attorney?.name || "—"}</td></tr>
            </tbody>
          </table>
        </div>

        {c.client && (
          <div className="detail-section">
            <h3>Client</h3>
            <table className="detail-table">
              <tbody>
                <tr><td>Name</td><td>{c.client.name}</td></tr>
                <tr><td>Type</td><td>{c.client.type || "—"}</td></tr>
                {c.client.primary_email_address && (
                  <tr><td>Email</td><td>{c.client.primary_email_address}</td></tr>
                )}
                {c.client.primary_phone_number && (
                  <tr><td>Phone</td><td>{c.client.primary_phone_number}</td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="report-actions">
        <h3>Generate Report</h3>
        {error && <p className="error">{error}</p>}
        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={generating}
        >
          {generating ? "Generating..." : "Generate Case Summary PDF"}
        </button>

        {generatedReport && (
          <div className="report-success">
            <p>Report generated successfully!</p>
            <a
              href={getReportDownloadUrl(generatedReport.id)}
              className="btn btn-secondary"
              target="_blank"
              rel="noopener noreferrer"
            >
              Download PDF
            </a>
          </div>
        )}
      </div>
    </section>
  );
}
