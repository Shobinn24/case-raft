import { useState } from "react";
import { generateFirmReport, getReportDownloadUrl } from "../services/api";

export default function TrustReport() {
  const [generating, setGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState(null);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    setGeneratedReport(null);
    try {
      // Trust report is a current snapshot — no date range needed.
      // We still call generateFirmReport but pass dummy dates since
      // the backend skips date validation for trust_management type.
      const today = new Date().toISOString().slice(0, 10);
      const res = await generateFirmReport(
        today,
        today,
        "trust_management",
        {}
      );
      setGeneratedReport(res.data.report);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <h2>Trust Management Report</h2>
      <p className="page-subtitle">
        Generate a report showing clients whose trust account balances are below
        the required threshold. Identifies both TCP (Trust Commitment Program)
        and non-TCP clients that need trust replenishment.
      </p>

      <div className="detail-section">
        <h3>How It Works</h3>
        <ul className="trust-info-list">
          <li>
            <strong>Non-TCP Clients:</strong> Trust needs replenishing when the
            balance drops below the initial trust deposit amount.
          </li>
          <li>
            <strong>TCP Clients:</strong> Trust needs replenishing when the
            balance drops below the minimum threshold set in Clio billing
            preferences.
          </li>
        </ul>
        <p className="trust-note">
          This report is a current snapshot of all open matters. No date range
          is needed.
        </p>
      </div>

      <div className="report-actions mt-24">
        {error && <p className="error">{error}</p>}
        <div className="btn-group">
          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "Generating..." : "Generate Trust Report"}
          </button>
        </div>

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
    </div>
  );
}
