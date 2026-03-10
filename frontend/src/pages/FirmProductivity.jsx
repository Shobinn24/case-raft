import { useState } from "react";
import { generateFirmReport, getReportDownloadUrl } from "../services/api";

export default function FirmProductivity() {
  // Default to current month
  const today = new Date().toISOString().slice(0, 10);
  const firstOfMonth = new Date(
    new Date().getFullYear(),
    new Date().getMonth(),
    1
  )
    .toISOString()
    .slice(0, 10);

  const [startDate, setStartDate] = useState(firstOfMonth);
  const [endDate, setEndDate] = useState(today);
  const [generating, setGenerating] = useState(false);
  const [generatedReport, setGeneratedReport] = useState(null);
  const [error, setError] = useState(null);

  const handleGenerate = async () => {
    if (!startDate || !endDate) {
      setError("Please select both a start and end date.");
      return;
    }
    setGenerating(true);
    setError(null);
    setGeneratedReport(null);
    try {
      const res = await generateFirmReport(startDate, endDate);
      setGeneratedReport(res.data.report);
    } catch (err) {
      setError(err.response?.data?.error || "Failed to generate report");
    } finally {
      setGenerating(false);
    }
  };

  return (
    <div>
      <h2>Firm Productivity Report</h2>
      <p style={{ color: "#666", marginBottom: 24 }}>
        Generate a report showing hours billed by each employee and
        corresponding revenue for a selected date range.
      </p>

      <div className="detail-section">
        <h3>Select Date Range</h3>
        <div className="date-range-form">
          <label>
            Start Date
            <input
              type="date"
              value={startDate}
              onChange={(e) => setStartDate(e.target.value)}
            />
          </label>
          <label>
            End Date
            <input
              type="date"
              value={endDate}
              onChange={(e) => setEndDate(e.target.value)}
            />
          </label>
        </div>
      </div>

      <div className="report-actions" style={{ marginTop: 24 }}>
        {error && <p className="error">{error}</p>}
        <button
          className="btn btn-primary"
          onClick={handleGenerate}
          disabled={generating}
        >
          {generating ? "Generating..." : "Generate Firm Productivity PDF"}
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
    </div>
  );
}
