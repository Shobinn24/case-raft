import { useState } from "react";
import { generateFirmReport, getReportDownloadUrl } from "../services/api";

export default function RevenueReport() {
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
  const [mode, setMode] = useState("collected");
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
      const res = await generateFirmReport(
        startDate,
        endDate,
        "revenue_by_practice_area",
        { mode }
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
      <h2>Revenue by Practice Area</h2>
      <p className="page-subtitle">
        Generate a report showing revenue collected or outstanding AR broken
        down by area of law and aging buckets (1-30, 31-60, 61-90, 91+ days).
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

      <div className="detail-section">
        <h3>Report Mode</h3>
        <div className="section-picker">
          <label className="section-checkbox">
            <input
              type="radio"
              name="mode"
              checked={mode === "collected"}
              onChange={() => setMode("collected")}
            />
            Collected Revenue (Paid)
          </label>
          <label className="section-checkbox">
            <input
              type="radio"
              name="mode"
              checked={mode === "outstanding"}
              onChange={() => setMode("outstanding")}
            />
            Outstanding AR (Unpaid)
          </label>
        </div>
      </div>

      <div className="report-actions mt-24">
        {error && <p className="error">{error}</p>}
        <div className="btn-group">
          <button
            className="btn btn-primary"
            onClick={handleGenerate}
            disabled={generating}
          >
            {generating ? "Generating..." : "Generate PDF Report"}
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
